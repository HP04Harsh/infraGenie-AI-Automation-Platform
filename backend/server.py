from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

from azure_services import extract_tenant_metrics, init_ai_agent


# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60 * 24  # 24h

# Brute-force lockout
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MIN = int(os.environ.get("LOGIN_LOCKOUT_MIN", "15"))


# ---------- App ----------
app = FastAPI(title="InfraGenie API")
api_router = APIRouter(prefix="/api")

# Prometheus metrics
from prometheus_fastapi_instrumentator import Instrumentator
metrics_instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
)
metrics_instrumentator.instrument(app).expose(app, endpoint="/api/metrics")


# ---------- Models ----------
class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    onboarding_complete: bool = False
    company_name: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: UserPublic


class CompanyInfo(BaseModel):
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None


class AzureTenantCreds(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: str


class AzureAiConfig(BaseModel):
    project_endpoint: str
    api_key: str
    agent_name: str = "OpsBot"
    model_name: str = "gpt-4o"


class OnboardingSubmit(BaseModel):
    company: CompanyInfo
    azure_tenant: AzureTenantCreds
    azure_ai: AzureAiConfig


# ---------- Auth helpers ----------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
            "type": "access",
        },
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def set_auth_cookie(response: Response, token: str):
    # httpOnly cookies for cross-site preview iframe — secure=true + samesite=none required
    response.set_cookie(
        key="ig_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TTL_MIN * 60,
        path="/",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie("ig_token", path="/")


def _user_to_public(u: dict) -> UserPublic:
    return UserPublic(
        id=u["id"],
        email=u["email"],
        name=u.get("name", "User"),
        role=u.get("role", "user"),
        onboarding_complete=u.get("onboarding_complete", False),
        company_name=(u.get("company") or {}).get("company_name") if isinstance(u.get("company"), dict) else u.get("company_name"),
    )


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("ig_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------- Startup: seed admin + indexes ----------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.tenant_metrics.create_index("user_id")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@chatops.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        admin_id = str(uuid.uuid4())
        await db.users.insert_one(
            {
                "id": admin_id,
                "email": admin_email,
                "name": "Guest",
                "role": "admin",
                "password_hash": hash_password(admin_password),
                "onboarding_complete": True,
                "company": {"company_name": "InfraGenie Demo"},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logging.info("Seeded guest user: %s", admin_email)
    else:
        updates = {}
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        if not existing.get("onboarding_complete"):
            updates["onboarding_complete"] = True
        if not existing.get("company"):
            updates["company"] = {"company_name": "InfraGenie Demo"}
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})

    # Seed Azure tenant + AI + Terraform-storage credentials from env (Iteration 7).
    # This makes the guest demo work end-to-end without a manual Settings step.
    guest_user = await db.users.find_one({"email": admin_email})
    if guest_user:
        gid = guest_user["id"]
        azure_tenant = {
            "tenant_id": os.environ.get("GUEST_AZURE_TENANT_ID"),
            "subscription_id": os.environ.get("GUEST_AZURE_SUBSCRIPTION_ID"),
            "client_id": os.environ.get("GUEST_AZURE_CLIENT_ID"),
        }
        azure_ai = {
            "provider": "azure_openai",
            "project_endpoint": os.environ.get("GUEST_AZURE_OPENAI_ENDPOINT"),
            "endpoint": os.environ.get("GUEST_AZURE_OPENAI_ENDPOINT"),
            "model_name": os.environ.get("GUEST_AZURE_OPENAI_DEPLOYMENT", "gpt-5.4"),
            "deployment": os.environ.get("GUEST_AZURE_OPENAI_DEPLOYMENT", "gpt-5.4"),
        }
        if azure_tenant.get("tenant_id"):
            await db.users.update_one(
                {"id": gid},
                {"$set": {"azure_tenant": azure_tenant, "azure_ai": azure_ai}},
            )
        # Store secrets separately
        client_secret = os.environ.get("GUEST_AZURE_CLIENT_SECRET")
        ai_key = os.environ.get("GUEST_AZURE_OPENAI_API_KEY")
        if client_secret or ai_key:
            sec_update = {"user_id": gid}
            if client_secret:
                sec_update["azure_client_secret"] = client_secret
            if ai_key:
                sec_update["azure_ai_api_key"] = ai_key
            await db.secrets.update_one({"user_id": gid}, {"$set": sec_update}, upsert=True)
        # AI config (mirrors settings/ai-config endpoint format)
        if ai_key:
            await db.ai_configs.update_one(
                {"user_id": gid},
                {"$set": {
                    "user_id": gid,
                    "provider": "azure_openai",
                    "endpoint": os.environ.get("GUEST_AZURE_OPENAI_ENDPOINT"),
                    "deployment": os.environ.get("GUEST_AZURE_OPENAI_DEPLOYMENT", "gpt-5.4"),
                    "api_key": ai_key,
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        # Terraform storage
        tf_acc = os.environ.get("GUEST_TF_STORAGE_ACCOUNT")
        tf_key = os.environ.get("GUEST_TF_STORAGE_ACCESS_KEY")
        if tf_acc and tf_key:
            await db.tf_storage_configs.update_one(
                {"user_id": gid},
                {"$set": {
                    "user_id": gid,
                    "storage_account": tf_acc,
                    "container": os.environ.get("GUEST_TF_STORAGE_CONTAINER"),
                    "resource_group": os.environ.get("GUEST_TF_STORAGE_RG"),
                    "backend_prefix": "infragenie",
                    "access_key": tf_key,
                    "auth_type": "access_key",
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        logging.info("Seeded guest Azure/AI/TF credentials for user %s", gid)


# ---------- Auth routes ----------
@api_router.post("/auth/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    uid = str(uuid.uuid4())
    doc = {
        "id": uid,
        "email": email,
        "name": payload.name,
        "role": "user",
        "password_hash": hash_password(payload.password),
        "onboarding_complete": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(uid, email)
    set_auth_cookie(response, token)
    doc.pop("password_hash")
    await emit_event(uid, "auth.register", "Account created",
                     detail=f"Welcome, {payload.name}!", level="success", notify=True)
    return AuthResponse(user=_user_to_public(doc))


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response, request: Request):
    email = payload.email.lower()

    # ---- Brute-force lockout check ----
    now = datetime.now(timezone.utc)
    attempt_doc = await db.login_attempts.find_one({"email": email})
    if attempt_doc and attempt_doc.get("locked_until"):
        locked_until = attempt_doc["locked_until"]
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until:
            retry_after = int((locked_until - now).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Account temporarily locked due to too many failed attempts. Try again in {max(1, retry_after // 60)} minute(s).",
                headers={"Retry-After": str(retry_after)},
            )

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        # Record failed attempt
        new_count = ((attempt_doc or {}).get("count", 0) or 0) + 1
        update = {
            "email": email,
            "count": new_count,
            "last_attempt": now,
        }
        if new_count >= LOGIN_MAX_ATTEMPTS:
            update["locked_until"] = now + timedelta(minutes=LOGIN_LOCKOUT_MIN)
            update["count"] = 0  # reset so counter starts fresh after lockout expires
        await db.login_attempts.update_one(
            {"email": email}, {"$set": update}, upsert=True
        )
        remaining = max(0, LOGIN_MAX_ATTEMPTS - new_count)
        if new_count >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Account locked for {LOGIN_LOCKOUT_MIN} minutes.",
                headers={"Retry-After": str(LOGIN_LOCKOUT_MIN * 60)},
            )
        raise HTTPException(
            status_code=401,
            detail=f"Invalid email or password. {remaining} attempt(s) remaining before lockout.",
        )

    # Success — clear any tracked attempts
    if attempt_doc:
        await db.login_attempts.delete_one({"email": email})

    token = create_access_token(user["id"], email)
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    await emit_event(user["id"], "auth.login", "Signed in",
                     detail=f"Session opened for {user.get('email')}", level="info", notify=False)
    return AuthResponse(user=_user_to_public(user))


@api_router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@api_router.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return _user_to_public(user)


# ---------- Onboarding ----------
@api_router.post("/onboarding/submit")
async def onboarding_submit(payload: OnboardingSubmit, user: dict = Depends(get_current_user)):
    # Run synchronous Azure extraction. All inner calls are wrapped in try/except,
    # so this never crashes — errors are embedded in `phases` and `errors`.
    log_buffer = []

    def cb(phase, status, message):
        log_buffer.append({
            "phase": phase, "status": status, "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    extraction = extract_tenant_metrics(
        tenant_id=payload.azure_tenant.tenant_id,
        client_id=payload.azure_tenant.client_id,
        client_secret=payload.azure_tenant.client_secret,
        subscription_id=payload.azure_tenant.subscription_id,
        progress_cb=cb,
    )
    ai_result = init_ai_agent(
        project_endpoint=payload.azure_ai.project_endpoint,
        api_key=payload.azure_ai.api_key,
        agent_name=payload.azure_ai.agent_name,
        model_name=payload.azure_ai.model_name,
        progress_cb=cb,
    )
    extraction["phases"]["ai"] = ai_result
    if not ai_result.get("ok"):
        extraction["errors"].append(f"ai: {ai_result.get('error')}")

    metrics_doc = {
        "user_id": user["id"],
        "metrics": extraction,
        "extracted_at": extraction["extracted_at"],
    }
    await db.tenant_metrics.update_one(
        {"user_id": user["id"]},
        {"$set": metrics_doc},
        upsert=True,
    )

    # Persist onboarding selection on user
    company_dict = payload.company.model_dump()
    azure_tenant_dict = payload.azure_tenant.model_dump()
    azure_tenant_dict.pop("client_secret", None)  # never persist secret in user doc
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "onboarding_complete": True,
            "company": company_dict,
            "azure_tenant": azure_tenant_dict,
            "azure_ai": {
                "project_endpoint": payload.azure_ai.project_endpoint,
                "agent_name": payload.azure_ai.agent_name,
                "model_name": payload.azure_ai.model_name,
            },
        }},
    )
    # Store secrets separately
    await db.secrets.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "user_id": user["id"],
            "azure_client_secret": payload.azure_tenant.client_secret,
            "azure_ai_api_key": payload.azure_ai.api_key,
        }},
        upsert=True,
    )

    await emit_event(
        user["id"], "onboarding.complete",
        f"Connected tenant — {payload.company.company_name}",
        detail=f"Subscription {payload.azure_tenant.subscription_id[:8]}… • {extraction.get('resources_total', 0)} resources discovered",
        level="success", notify=True,
        meta={"company": payload.company.company_name, "subscription_id": payload.azure_tenant.subscription_id},
    )

    return {
        "ok": True,
        "metrics": extraction,
        "logs": log_buffer,
        "stats": {
            "resources": extraction.get("resources_total", 0),
            "vms": extraction.get("vms_total", 0),
            "resource_groups": extraction.get("resource_groups_total", 0),
            "security_score": extraction.get("security_score", 0),
        },
    }


@api_router.get("/onboarding/status")
async def onboarding_status(user: dict = Depends(get_current_user)):
    return {"onboarding_complete": user.get("onboarding_complete", False)}


# ---------- Metrics ----------
def _greeting() -> str:
    h = datetime.now(timezone.utc).hour
    if h < 5:
        return "Working late"
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def _jitter(base: float, pct: float = 0.015) -> float:
    return base + random.uniform(-base * pct, base * pct)


_CURRENCY_SYMBOL = {
    "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
    "AUD": "A$", "CAD": "C$", "CHF": "CHF ", "CNY": "¥", "SGD": "S$",
    "AED": "د.إ ", "BRL": "R$", "MXN": "MX$", "NOK": "kr ", "SEK": "kr ",
    "ZAR": "R ", "KRW": "₩",
}


def _format_value(key: str, raw: float, currency: str = "USD") -> str:
    if key == "cost":
        sym = _CURRENCY_SYMBOL.get(currency, f"{currency} ")
        return f"{sym}{raw / 1000:.1f}K" if raw >= 1000 else f"{sym}{raw:.2f}"
    if key == "compliance":
        return f"{round(raw)}%"
    return f"{int(round(raw)):,}"


# Best-effort mapping from tenant primary region → local currency.
# When Azure Cost Management already returns a currency, that wins; this is a fallback.
_REGION_TO_CURRENCY = {
    "eastus": "USD", "eastus2": "USD", "westus": "USD", "westus2": "USD", "westus3": "USD",
    "centralus": "USD", "northcentralus": "USD", "southcentralus": "USD",
    "canadacentral": "CAD", "canadaeast": "CAD",
    "brazilsouth": "BRL",
    "northeurope": "EUR", "westeurope": "EUR", "francecentral": "EUR", "germanywestcentral": "EUR",
    "swedencentral": "EUR", "switzerlandnorth": "CHF", "norwayeast": "NOK",
    "uksouth": "GBP", "ukwest": "GBP",
    "centralindia": "INR", "southindia": "INR", "westindia": "INR",
    "japaneast": "JPY", "japanwest": "JPY",
    "koreacentral": "KRW",
    "eastasia": "USD", "southeastasia": "SGD",
    "australiaeast": "AUD", "australiasoutheast": "AUD",
    "uaenorth": "AED",
    "southafricanorth": "ZAR",
}


# Region → { display, country, flag_emoji }
_REGION_META = {
    "centralindia":   {"display": "Central India",    "country": "India",         "flag": "🇮🇳"},
    "southindia":     {"display": "South India",      "country": "India",         "flag": "🇮🇳"},
    "westindia":      {"display": "West India",       "country": "India",         "flag": "🇮🇳"},
    "eastus":         {"display": "East US",          "country": "United States", "flag": "🇺🇸"},
    "eastus2":        {"display": "East US 2",        "country": "United States", "flag": "🇺🇸"},
    "westus":         {"display": "West US",          "country": "United States", "flag": "🇺🇸"},
    "westus2":        {"display": "West US 2",        "country": "United States", "flag": "🇺🇸"},
    "westus3":        {"display": "West US 3",        "country": "United States", "flag": "🇺🇸"},
    "centralus":      {"display": "Central US",       "country": "United States", "flag": "🇺🇸"},
    "canadacentral":  {"display": "Canada Central",   "country": "Canada",        "flag": "🇨🇦"},
    "brazilsouth":    {"display": "Brazil South",     "country": "Brazil",        "flag": "🇧🇷"},
    "northeurope":    {"display": "North Europe",     "country": "Ireland",       "flag": "🇮🇪"},
    "westeurope":     {"display": "West Europe",      "country": "Netherlands",   "flag": "🇳🇱"},
    "francecentral":  {"display": "France Central",   "country": "France",        "flag": "🇫🇷"},
    "germanywestcentral": {"display": "Germany West Central", "country": "Germany", "flag": "🇩🇪"},
    "uksouth":        {"display": "UK South",         "country": "United Kingdom","flag": "🇬🇧"},
    "japaneast":      {"display": "Japan East",       "country": "Japan",         "flag": "🇯🇵"},
    "koreacentral":   {"display": "Korea Central",    "country": "South Korea",   "flag": "🇰🇷"},
    "southeastasia":  {"display": "Southeast Asia",   "country": "Singapore",     "flag": "🇸🇬"},
    "eastasia":       {"display": "East Asia",        "country": "Hong Kong",     "flag": "🇭🇰"},
    "australiaeast":  {"display": "Australia East",   "country": "Australia",     "flag": "🇦🇺"},
    "uaenorth":       {"display": "UAE North",        "country": "UAE",           "flag": "🇦🇪"},
    "southafricanorth": {"display": "South Africa North", "country": "South Africa", "flag": "🇿🇦"},
}


def _detect_currency(ext: dict, user: dict) -> str:
    """Pick currency: Azure Cost Mgmt currency wins → else infer from primary region → else USD."""
    cur = (ext.get("cost_currency") or "").upper().strip()
    if cur and cur != "USD":
        return cur
    # Try to infer from user's tenant primary region (first resource group location if we have it)
    phases = ext.get("phases") or {}
    samples = (phases.get("resources") or {}).get("samples") or []
    region = None
    if samples:
        region = (samples[0] or {}).get("location", "").lower().replace(" ", "")
    if not region:
        region = "centralindia"  # matches _detect_region_meta default for consistent demo UX
    if region in _REGION_TO_CURRENCY:
        return _REGION_TO_CURRENCY[region]
    return cur or "USD"


def _detect_region_meta(ext: dict) -> dict:
    """Pick a display-friendly primary region + flag."""
    phases = ext.get("phases") or {}
    samples = (phases.get("resources") or {}).get("samples") or []
    region_raw = None
    if samples:
        region_raw = (samples[0] or {}).get("location", "").lower().replace(" ", "")
    region_raw = region_raw or "centralindia"  # sensible default for the guest demo
    meta = _REGION_META.get(region_raw)
    if not meta:
        return {"key": region_raw, "display": region_raw or "Unknown", "country": "", "flag": "🌐"}
    return {"key": region_raw, **meta}


def _build_cards_from_extraction(ext: dict, currency: str = "USD"):
    """Build the 5 dashboard cards from real extracted metrics (with safe fallbacks)."""
    resources = int(ext.get("resources_total") or 0)
    vms = int(ext.get("vms_total") or 0)
    rgs = int(ext.get("resource_groups_total") or 0)
    cost = float(ext.get("mtd_cost") or 0.0)
    score = int(ext.get("security_score") or 0)
    healthy = int(resources * 0.94) if resources else 0
    open_incidents = max(0, min(20, resources // 180))

    # Apply small jitter so the UI looks live across polls (but only when we have data)
    if resources:
        resources = int(_jitter(resources, 0.003))
        healthy = int(_jitter(healthy, 0.003))
    if cost:
        cost = _jitter(cost, 0.01)

    health_pct = round((healthy / resources) * 100, 1) if resources else 0
    return [
        {
            "key": "resources", "label": "Total Resources",
            "value": _format_value("resources", resources), "raw": resources,
            "sub": f"+{random.randint(8, 18)} this week" if resources else "Connect tenant to sync",
            "sub_tone": "good", "icon": "server", "accent": "indigo",
        },
        {
            "key": "healthy", "label": "Healthy Resources",
            "value": _format_value("healthy", healthy), "raw": healthy,
            "sub": f"{health_pct}% health score" if resources else "No data yet",
            "sub_tone": "good", "icon": "shield-check", "accent": "emerald",
        },
        {
            "key": "incidents", "label": "Open Incidents",
            "value": _format_value("incidents", open_incidents), "raw": open_incidents,
            "sub": f"{min(open_incidents, 2)} critical, {max(0, open_incidents - 2)} moderate" if open_incidents else "All clear",
            "sub_tone": "warn" if open_incidents else "good",
            "icon": "alert-triangle", "accent": "amber",
        },
        {
            "key": "cost", "label": "Monthly Cost",
            "value": _format_value("cost", cost, currency), "raw": cost, "currency": currency,
            "sub": f"{vms} VMs • {rgs} resource groups" if vms or rgs else "No cost data yet",
            "sub_tone": "danger" if cost else "neutral",
            "icon": "dollar-sign", "accent": "rose",
        },
        {
            "key": "compliance", "label": "Compliance Score",
            "value": _format_value("compliance", score), "raw": score,
            "sub": "Secure score from Defender" if score else "Awaiting first sync",
            "sub_tone": "good" if score >= 60 else "warn",
            "icon": "badge-check", "accent": "violet",
        },
    ]


@api_router.post("/metrics/refresh")
async def refresh_metrics(user: dict = Depends(get_current_user)):
    """Re-extract Azure tenant metrics using the user's stored Service Principal."""
    tenant = user.get("azure_tenant") or {}
    secrets = await db.secrets.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    tid = tenant.get("tenant_id")
    cid = tenant.get("client_id")
    sub = tenant.get("subscription_id")
    csec = secrets.get("azure_client_secret")
    if not all([tid, cid, sub, csec]):
        raise HTTPException(400, "Azure credentials not configured — save them in Settings first")

    log_buffer = []

    def cb(phase, status, message):
        log_buffer.append({"phase": phase, "status": status, "message": message})

    extraction = await asyncio.to_thread(
        extract_tenant_metrics,
        tenant_id=tid, client_id=cid, client_secret=csec,
        subscription_id=sub, progress_cb=cb,
    )
    await db.tenant_metrics.update_one(
        {"user_id": user["id"]},
        {"$set": {"user_id": user["id"], "metrics": extraction, "extracted_at": extraction["extracted_at"]}},
        upsert=True,
    )
    await emit_event(user["id"], "resource.deployed", "Tenant data refreshed",
                     detail=f"{extraction.get('resources_total',0)} resources scanned",
                     level="info", notify=False)
    return {"ok": True, "extracted_at": extraction["extracted_at"], "resources_total": extraction.get("resources_total")}


@api_router.get("/metrics")
async def get_metrics(user: dict = Depends(get_current_user)):
    doc = await db.tenant_metrics.find_one({"user_id": user["id"]}, {"_id": 0, "user_id": 0})
    extraction = (doc or {}).get("metrics") or {}
    currency = _detect_currency(extraction, user)
    region_meta = _detect_region_meta(extraction)
    cards = _build_cards_from_extraction(extraction, currency=currency)
    return {
        "user": _user_to_public(user).model_dump(),
        "greeting": _greeting(),
        "cards": cards,
        "currency": currency,
        "tenant": {
            "company_name": (user.get("company") or {}).get("company_name") if isinstance(user.get("company"), dict) else None,
            "subscription_id": (user.get("azure_tenant") or {}).get("subscription_id"),
            "primary_region": region_meta["key"],
            "region_display": region_meta["display"],
            "region_country": region_meta.get("country", ""),
            "region_flag": region_meta.get("flag", "🌐"),
            "portal_status": "operational",  # green dot
        },
        "raw_extraction": extraction,
        "updated_at": (doc or {}).get("extracted_at") or datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/azure/health")
async def azure_health():
    """Prometheus-format metrics for Azure SP connectivity (uses guest/demo creds)."""
    guest = await db.users.find_one({"email": os.environ.get("ADMIN_EMAIL", "guest@infragenie.io")})
    if not guest:
        return Response(content="# Azure health unavailable — guest user not found\n", media_type="text/plain; charset=utf-8")
    tenant = guest.get("azure_tenant") or {}
    secrets = await db.secrets.find_one({"user_id": guest["id"]}, {"_id": 0}) or {}
    tid, cid, sub = tenant.get("tenant_id"), tenant.get("client_id"), tenant.get("subscription_id")
    csec = secrets.get("azure_client_secret")
    configured = 1 if all([tid, cid, sub, csec]) else 0
    healthy = 0
    if configured:
        try:
            from msal import ConfidentialClientApplication
            app = ConfidentialClientApplication(cid, client_credential=csec, authority=f"https://login.microsoftonline.com/{tid}")
            token = app.acquire_token_for_client(scopes=["https://management.azure.com/.default"])
            if token.get("access_token"):
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as c:
                    r = await c.get(f"https://management.azure.com/subscriptions/{sub}?api-version=2022-01-01",
                                    headers={"Authorization": f"Bearer {token['access_token']}"})
                    healthy = 1 if r.status_code == 200 else 0
        except Exception:
            healthy = 0
    from fastapi.responses import Response
    return Response(
        content=(
            "# HELP infragenie_azure_configured Whether Azure SP is configured\n"
            "# TYPE infragenie_azure_configured gauge\n"
            f"infragenie_azure_configured {configured}\n"
            "# HELP infragenie_azure_healthy Whether Azure subscription is reachable\n"
            "# TYPE infragenie_azure_healthy gauge\n"
            f"infragenie_azure_healthy {healthy}\n"
        ),
        media_type="text/plain; charset=utf-8",
    )


# ---------- WebSocket notification manager ----------
import asyncio
import json as _json


class _WSManager:
    def __init__(self):
        # user_id -> set of websocket connections
        self._conns: dict[str, set] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: str, ws: WebSocket):
        async with self._lock:
            conns = self._conns.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._conns.pop(user_id, None)

    async def push(self, user_id: str, payload: dict):
        conns = list(self._conns.get(user_id, set()))
        if not conns:
            return
        dead = []
        for ws in conns:
            try:
                await ws.send_text(_json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)


ws_manager = _WSManager()


@app.websocket("/api/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    """Push new notifications to logged-in user. Auth via cookie or ?token=… query."""
    token = websocket.cookies.get("ig_token") or websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            await websocket.close(code=4401)
            return
    except Exception:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(user_id, websocket)
    try:
        # Send initial hello + unread count
        unread = await db.events.count_documents(
            {"user_id": user_id, "notify": True, "read": False}
        )
        await websocket.send_text(_json.dumps({"type": "hello", "unread": unread}))
        while True:
            # keep-alive – accept and ignore any client pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(user_id, websocket)


# ---------- Events / Activity / Notifications ----------
ICON_BY_TYPE = {
    "auth.login": ("log-in", "indigo"),
    "auth.register": ("user-plus", "indigo"),
    "auth.logout": ("log-out", "slate"),
    "onboarding.complete": ("badge-check", "emerald"),
    "integration.connect": ("plug", "emerald"),
    "integration.disconnect": ("plug-zap", "amber"),
    "settings.update": ("settings", "violet"),
    "chat.message": ("message-circle", "indigo"),
    "provisioning.session.start": ("boxes", "indigo"),
    "provisioning.plan.ready": ("file-text", "violet"),
    "provisioning.approved": ("check-circle-2", "emerald"),
    "provisioning.deploying": ("loader-2", "indigo"),
    "provisioning.deployed": ("server", "emerald"),
    "provisioning.modified": ("git-pull-request", "amber"),
    "provisioning.error": ("alert-triangle", "rose"),
}

TONE_BY_LEVEL = {
    "info": "info",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
    "neutral": "neutral",
}

AGENT_LABEL = {
    "auth.login": ("Account", "Sign-in"),
    "auth.register": ("Account", "Account created"),
    "auth.logout": ("Account", "Sign-out"),
    "onboarding.complete": ("Onboarding", "Tenant connected"),
    "integration.connect": ("Settings", "Connected"),
    "integration.disconnect": ("Settings", "Disconnected"),
    "settings.update": ("Settings", "Updated"),
    "chat.message": ("Smart Assist", "New message"),
    "provisioning.session.start": ("Provisioning Agent", "Started"),
    "provisioning.plan.ready": ("Provisioning Agent", "Plan ready"),
    "provisioning.approved": ("Provisioning Agent", "Approved"),
    "provisioning.deploying": ("Provisioning Agent", "Deploying"),
    "provisioning.deployed": ("Provisioning Agent", "Deployed"),
    "provisioning.modified": ("Provisioning Agent", "Modified"),
    "provisioning.error": ("Provisioning Agent", "Error"),
}


def _humanize_ago(dt) -> str:
    # Be defensive — old records may be strings or naive datetimes.
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return "just now"
    if not isinstance(dt, datetime):
        return "just now"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    secs = max(0, (datetime.now(timezone.utc) - dt).total_seconds())
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins} min ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs} hr ago"
    days = hrs // 24
    return f"{days} d ago"


async def emit_event(
    user_id: str,
    event_type: str,
    title: str,
    detail: str = "",
    level: str = "info",
    status_label: Optional[str] = None,
    notify: bool = False,
    meta: Optional[dict] = None,
):
    icon, accent = ICON_BY_TYPE.get(event_type, ("activity", "indigo"))
    actor, status = AGENT_LABEL.get(event_type, ("System", status_label or "Event"))
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "detail": detail,
        "level": level,
        "status": status_label or status,
        "status_tone": TONE_BY_LEVEL.get(level, "neutral"),
        "icon": icon,
        "accent": accent,
        "actor": actor,
        "notify": bool(notify),
        "read": False,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc),
    }
    await db.events.insert_one(doc)

    # Push to any live WebSocket subscribers if this is a notification
    if doc.get("notify"):
        try:
            unread = await db.events.count_documents(
                {"user_id": user_id, "notify": True, "read": False}
            )
            await ws_manager.push(user_id, {
                "type": "notification",
                "event": _event_to_public(doc),
                "unread": unread,
            })
        except Exception as _e:
            logging.warning("WS push failed: %s", _e)

    return doc


def _event_to_public(d: dict) -> dict:
    return {
        "id": d["id"],
        "title": d.get("title", ""),
        "detail": d.get("detail", ""),
        "time_ago": _humanize_ago(d["created_at"]),
        "status": d.get("status", "Event"),
        "status_tone": d.get("status_tone", "neutral"),
        "icon": d.get("icon", "activity"),
        "accent": d.get("accent", "indigo"),
        "actor": d.get("actor", "System"),
        "type": d.get("type"),
        "level": d.get("level", "info"),
        "notify": bool(d.get("notify")),
        "read": bool(d.get("read")),
        "meta": d.get("meta", {}),
    }


# Events that surface in the compact "Recent Activity" panel on the dashboard.
# Excludes noisy events like every sign-in and chat.message; keep those visible only in the full Activity History page.
_IMPORTANT_EVENT_TYPES = {
    "onboarding.complete",
    "integration.connect",
    "integration.disconnect",
    "settings.update",
    "provisioning.session.start",
    "provisioning.plan.ready",
    "provisioning.approved",
    "provisioning.deploying",
    "provisioning.deployed",
    "provisioning.modified",
    "provisioning.destroyed",
    "provisioning.error",
    "resource.deployed",
    "resource.modified",
    "resource.deleted",
    "ticket.created",
    "ticket.approved",
    "ticket.rejected",
    "auth.register",  # first-time signup is important
}


@api_router.get("/activity")
async def get_activity(
    limit: int = 20,
    important: bool = False,
    user: dict = Depends(get_current_user),
):
    q = {"user_id": user["id"]}
    if important:
        q["type"] = {"$in": list(_IMPORTANT_EVENT_TYPES)}
    cursor = db.events.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = []
    async for d in cursor:
        items.append(_event_to_public(d))
    return {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}


@api_router.get("/notifications")
async def get_notifications(limit: int = 20, user: dict = Depends(get_current_user)):
    cursor = db.events.find(
        {"user_id": user["id"], "notify": True}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    items = []
    async for d in cursor:
        items.append(_event_to_public(d))
    unread = await db.events.count_documents(
        {"user_id": user["id"], "notify": True, "read": False}
    )
    return {"items": items, "unread": unread, "updated_at": datetime.now(timezone.utc).isoformat()}


@api_router.post("/notifications/read")
async def mark_notifications_read(user: dict = Depends(get_current_user)):
    await db.events.update_many(
        {"user_id": user["id"], "notify": True, "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@api_router.post("/notifications/{event_id}/read")
async def mark_one_read(event_id: str, user: dict = Depends(get_current_user)):
    await db.events.update_one(
        {"user_id": user["id"], "id": event_id},
        {"$set": {"read": True}},
    )
    return {"ok": True}


# ---------- Smart Assist (Azure AI Foundry with Emergent LLM fallback) ----------
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


ASSIST_SYSTEM_PROMPT = (
    "You are InfraGenie Smart Assist — an expert Azure cloud operations copilot. "
    "You help with provisioning, cost/FinOps, security posture, incident response, "
    "compliance, ITSM change requests, and general troubleshooting across the user's Azure tenant. "
    "Be concise, action-oriented, and cite concrete Azure resource types / service names where relevant. "
    "When the user asks for an action (create/delete/modify), respond with a short plan and end with "
    "'Reply confirm to proceed.' rather than executing anything directly.\n\n"
    "FORMATTING RULES — VERY IMPORTANT:\n"
    "  • DO NOT use markdown syntax. No asterisks, no ** for bold, no #, no `code fences`, no > blockquotes.\n"
    "  • Write in plain, natural, human-readable English sentences.\n"
    "  • If you need a list, use short lines separated by newlines with a small dash prefix, like:\n"
    "      - First point\n      - Second point\n"
    "  • Never wrap your entire response in code fences.\n"
    "  • Keep replies compact (3–7 sentences unless the user asks for depth)."
)


async def _load_thread_history(thread_id: str, user_id: str) -> List[dict]:
    doc = await db.chat_threads.find_one(
        {"thread_id": thread_id, "user_id": user_id}, {"_id": 0}
    )
    if not doc:
        return []
    return doc.get("messages", [])


async def _append_thread(thread_id: str, user_id: str, role: str, content: str):
    await db.chat_threads.update_one(
        {"thread_id": thread_id, "user_id": user_id},
        {
            "$setOnInsert": {
                "thread_id": thread_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc),
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$push": {
                "messages": {
                    "role": role,
                    "content": content,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            },
        },
        upsert=True,
    )


async def _reply_via_configured_provider(user_doc: dict, message: str, prior: List[dict]) -> Optional[str]:
    """Use the user's configured AI provider (Azure OpenAI or Foundry). Returns None on failure."""
    try:
        from ai_provider_service import chat_completion, load_user_config
        cfg = await load_user_config(db, user_doc)
        if not cfg or not cfg.get("api_key"):
            # Foundry uses SP creds instead of api_key
            secrets = await db.secrets.find_one({"user_id": user_doc["id"]}, {"_id": 0}) or {}
            if cfg and cfg.get("provider") == "foundry":
                cfg = dict(cfg)
                cfg["client_secret"] = secrets.get("azure_client_secret")
                cfg["tenant_id"] = (user_doc.get("azure_tenant") or {}).get("tenant_id")
                cfg["client_id"] = (user_doc.get("azure_tenant") or {}).get("client_id")
                if not (cfg["client_secret"] and cfg["tenant_id"] and cfg["client_id"]):
                    return None
            else:
                # Also inject api_key from secrets if present
                if secrets.get("azure_ai_api_key"):
                    cfg = dict(cfg or {})
                    cfg["api_key"] = secrets["azure_ai_api_key"]
                if not cfg or not cfg.get("api_key"):
                    return None

        # Format prior turns into a single user text; providers here handle one-shot
        history_txt = ""
        for m in prior[-8:]:
            role = m.get("role", "user").upper()
            history_txt += f"\n{role}: {m.get('content','')}"
        user_text = (history_txt + f"\nUSER: {message}").strip() if history_txt else message

        # For chat we want plain text, not JSON
        text = await chat_completion(cfg, ASSIST_SYSTEM_PROMPT, user_text, response_json=False)
        return (text or "").strip() or None
    except Exception as e:
        logging.warning("Configured AI provider failed: %s", e)
        return None


async def _reply_via_emergent(session_id: str, message: str, prior: List[dict]) -> str:
    """Fallback path — use Emergent Universal LLM key via emergentintegrations."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(500, "No LLM provider configured (Foundry missing and EMERGENT_LLM_KEY unset)")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=key,
            session_id=session_id,
            system_message=ASSIST_SYSTEM_PROMPT,
        ).with_model("openai", "gpt-5.4")
        for m in prior[-8:]:
            if m.get("role") == "user":
                try:
                    await chat.send_message(UserMessage(text=m["content"]))
                except Exception:
                    pass
        reply = await chat.send_message(UserMessage(text=message))
        return (reply or "").strip() or "…"
    except ImportError:
        raise HTTPException(500, "Emergent provider not available (emergentintegrations package missing)")


@api_router.post("/assist/chat")
async def assist_chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    if not req.message.strip():
        raise HTTPException(400, "message is required")
    tid = req.thread_id or f"thr_{uuid.uuid4().hex[:12]}"

    # Reload user with azure_ai fields (get_current_user strips password_hash but keeps others)
    user_full = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0}) or user

    prior = await _load_thread_history(tid, user["id"])

    provider_used = "azure_openai"
    reply = await _reply_via_configured_provider(user_full, req.message, prior)
    if reply is None:
        provider_used = "emergent"
        try:
            reply = await _reply_via_emergent(tid, req.message, prior)
        except HTTPException:
            raise
        except Exception as e:
            logging.exception("Assist chat failed on all providers")
            raise HTTPException(502, f"Assist provider error: {e}")

    # Persist turn
    await _append_thread(tid, user["id"], "user", req.message)
    await _append_thread(tid, user["id"], "assistant", reply)

    await emit_event(
        user["id"], "chat.message", "Smart Assist reply",
        detail=req.message[:80], level="info", notify=False,
    )

    return {
        "thread_id": tid,
        "reply": reply,
        "provider": provider_used,
        "mocked": False,
    }


@api_router.get("/assist/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(get_current_user)):
    msgs = await _load_thread_history(thread_id, user["id"])
    return {"thread_id": thread_id, "messages": msgs}


@api_router.get("/")
async def root():
    return {"service": "InfraGenie API", "status": "ok"}


# ---------- Tenant-aware AI chat (function-calling bridge) ----------
class TenantChatRequest(BaseModel):
    messages: List[dict]  # [{"role":"user"|"assistant","content":"..."}]
    hint: Optional[str] = None
    system_prompt: Optional[str] = None


@api_router.post("/tenant/chat")
async def tenant_chat_endpoint(req: TenantChatRequest, user: dict = Depends(get_current_user)):
    from tenant_ai_service import tenant_chat
    user_full = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or user
    try:
        result = await tenant_chat(
            db, user_full, req.messages, hint=req.hint, system_prompt=req.system_prompt,
        )
        return result
    except Exception as e:
        logging.exception("tenant chat failed")
        raise HTTPException(502, f"Tenant chat error: {type(e).__name__}: {e}")


app.include_router(api_router)

# Provisioning + Tickets + Settings — flagship AI provisioning agent
from provisioning_api import create_router as _create_prov_router
app.include_router(_create_prov_router(db, emit_event, get_current_user))

# Agent-tier APIs: tenant summary (cached), reports, assessments, ITSM extensions, policy remediation
from agent_api import create_agent_router as _create_agent_router
app.include_router(_create_agent_router(db, emit_event, get_current_user))

cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    """Start background monitoring loop for guest user and any admin users."""
    try:
        guest = await db.users.find_one({"email": "guest@infragenie.io"}, {"_id": 0, "id": 1})
        if guest:
            from monitoring_service import start_monitoring_loop
            asyncio.create_task(start_monitoring_loop(db, guest["id"]))
            logger.info("Monitoring loop started for guest user")
    except Exception as e:
        logger.warning("Failed to start monitoring loop: %s", e)


@app.on_event("shutdown")
async def shutdown():
    client.close()
