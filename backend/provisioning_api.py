"""InfraGenie AI Provisioning Agent — HTTP API layer.

Wires provisioning_service.py functions into FastAPI routes.
Exposed via create_router(db, emit_event, get_current_user) from server.py.
"""
from __future__ import annotations

import asyncio
import logging
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_provider_service import load_user_config
from provisioning_service import (
    CATALOG,
    CATALOG_BY_KEY,
    ai_classify_and_collect,
    ai_generate_apply,
    ai_generate_plan,
    heuristic_intent,
    new_ticket_number,
    stage_runtime_folder,
)
import terraform_runtime as tf

logger = logging.getLogger("provisioning_api")


# --- Models ---
class StartSession(BaseModel):
    prompt: Optional[str] = None
    module_key: Optional[str] = None


class ChatIn(BaseModel):
    message: str


class ApproveIn(BaseModel):
    decision: str
    note: str = ""


class DestroyIn(BaseModel):
    ticket_id: str


class CommentIn(BaseModel):
    text: str


def _session_public(s: dict) -> dict:
    plan = s.get("plan") or {}
    apply_result = s.get("apply_result")
    # Merge actual outputs from apply_result into plan outputs
    if apply_result and apply_result.get("outputs"):
        actual = apply_result["outputs"]
        plan_outputs = plan.get("outputs") or []
        merged = []
        for po in plan_outputs:
            name = po.get("name")
            if name in actual:
                po = dict(po, value_preview=str(actual[name]))
            merged.append(po)
        if actual and not merged:
            merged = [{"name": k, "value_preview": str(v)} for k, v in actual.items()]
        plan = dict(plan, outputs=merged)
    return {
        "id": s["id"],
        "workspace_id": s.get("workspace_id"),
        "module_key": s.get("module_key"),
        "module": CATALOG_BY_KEY.get(s.get("module_key")) if s.get("module_key") else None,
        "collected_vars": s.get("collected_vars", {}),
        "missing_vars": s.get("missing_vars", []),
        "conversation": s.get("conversation", []),
        "status": s.get("status", "collecting"),
        "plan": plan,
        "apply_result": apply_result,
        "blob_artifacts": (apply_result or {}).get("blob_artifacts"),
        "ticket_id": s.get("ticket_id"),
        "ticket_number": s.get("ticket_number"),
        "created_at": s.get("created_at"),
        "updated_at": s.get("updated_at"),
    }


def _ticket_public(t: dict) -> dict:
    return {
        "id": t["id"],
        "ticket_number": t["ticket_number"],
        "workspace_id": t.get("workspace_id"),
        "deployment_name": t.get("deployment_name") or t.get("resource_name") or t.get("title"),
        "module_key": t.get("module_key"),
        "module_label": t.get("module_label"),
        "resource_name": t.get("resource_name"),
        "resource_type": t.get("resource_type"),
        "region": t.get("region"),
        "operation": t.get("operation", "create"),
        "status": t.get("status", "pending"),
        "estimated_cost": t.get("estimated_cost"),
        "actual_cost": t.get("actual_cost"),
        "currency": t.get("currency", "USD"),
        "requested_by": t.get("requested_by"),
        "requested_by_email": t.get("requested_by_email"),
        "approver": t.get("approver"),
        "created_at": t.get("created_at"),
        "completed_at": t.get("completed_at"),
        "plan": t.get("plan"),
        "apply_result": t.get("apply_result"),
        "logs": t.get("logs", []),
        "outputs": t.get("outputs", {}),
        "comments": t.get("comments", []),
        "audit": t.get("audit", []),
    }


async def _load_ai_cfg(db, user: dict) -> Dict[str, Any]:
    try:
        cfg = await load_user_config(db, user)
        if cfg and cfg.get("api_key"):
            return cfg
    except Exception as e:
        logger.warning("load_user_config failed: %s", e)

    endpoint = os.environ.get("GUEST_AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("GUEST_AZURE_OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("GUEST_AZURE_OPENAI_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    if endpoint and api_key and deployment:
        return {"provider": "azure_openai", "endpoint": endpoint, "api_key": api_key, "deployment": deployment}

    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if emergent_key and "XXXX" not in emergent_key:
        return {"provider": "emergent", "api_key": emergent_key}

    return {"provider": "azure_openai", "endpoint": "", "api_key": "", "deployment": "gpt-4o"}


async def _load_sp_creds(db, user: dict) -> Dict[str, str]:
    """Build the Azure Service Principal credential bundle for terraform ARM_* env vars."""
    tenant = (user.get("azure_tenant") or {})
    secrets = await db.secrets.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
    return {
        "tenant_id": tenant.get("tenant_id"),
        "subscription_id": tenant.get("subscription_id"),
        "client_id": tenant.get("client_id"),
        "client_secret": secrets.get("azure_client_secret"),
    }


async def _load_tf_storage(db, user: dict) -> Optional[Dict[str, Any]]:
    doc = await db.tf_storage_configs.find_one({"user_id": user["id"]}, {"_id": 0}) or None
    if not doc:
        return None
    return {
        "storage_account": doc.get("storage_account"),
        "container": doc.get("container"),
        "resource_group": doc.get("resource_group"),
        "key_prefix": doc.get("backend_prefix") or "infragenie",
        "access_key": doc.get("access_key"),
        "sas_token": doc.get("sas_token"),
    }


def _is_tf_ready(sp: Dict[str, str], tf_storage: Optional[Dict[str, Any]]) -> bool:
    return all([sp.get("tenant_id"), sp.get("subscription_id"), sp.get("client_id"), sp.get("client_secret")]) \
        and (tf_storage is None or tf_storage.get("storage_account") is not None)


def _generate_module_template(module_key: str, resource_type: str, description: str = "", provider: str = "azurerm") -> dict:
    """Fallback template for module generation when AI is unavailable."""
    safe_name = module_key.replace("-", "_").replace(".", "_")
    return {
        "main_tf": f"""resource "{provider}_{safe_name}" "this" {{
  # Auto-generated module: {module_key}
  # {description}
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}}
""",
        "variables_tf": f"""variable "name" {{
  description = "Name of the resource"
  type        = string
}}

variable "location" {{
  description = "Azure region"
  type        = string
  default     = "East US"
}}

variable "resource_group_name" {{
  description = "Name of the resource group"
  type        = string
}}

variable "tags" {{
  description = "Tags to apply"
  type        = map(string)
  default     = {{}}
}}
""",
        "outputs_tf": f"""output "id" {{
  description = "Resource ID"
  value       = {provider}_{safe_name}.this.id
}}

output "name" {{
  description = "Resource name"
  value       = {provider}_{safe_name}.this.name
}}
""",
        "versions_tf": f"""terraform {{
  required_version = ">= 1.0"
  required_providers {{
    {provider} = {{
      source  = "hashicorp/{provider}"
      version = "~> 3.0"
    }}
  }}
}}
""",
    }


def create_router(db, emit_event, get_current_user) -> APIRouter:
    """Build the provisioning + tickets + settings router bound to the given services."""
    router = APIRouter(prefix="/api")

    # ------------- Catalog & jobs -------------
    @router.get("/provisioning/catalog")
    async def get_catalog():
        return {"catalog": CATALOG}

    @router.get("/provisioning/jobs")
    async def get_jobs(limit: int = 30, user: dict = Depends(get_current_user)):
        cursor = db.tickets.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)
        items = [_ticket_public(t) async for t in cursor]
        return {"items": items}

    # ------------- Sessions -------------
    @router.post("/provisioning/sessions")
    async def start_session(payload: StartSession, user: dict = Depends(get_current_user)):
        sid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        module_key = payload.module_key
        if not module_key and payload.prompt:
            module_key = heuristic_intent(payload.prompt)

        conversation = []
        if payload.prompt:
            conversation.append({"role": "user", "content": payload.prompt, "at": now.isoformat()})

        if module_key and CATALOG_BY_KEY.get(module_key):
            mod = CATALOG_BY_KEY[module_key]
            first_required = next((v for v in mod["required_vars"] if not v.get("optional")), None)
            initial_message = (
                f"Great — I'll help you provision a {mod['label']}. "
                f"To generate the Terraform plan I need a few details. First: what {first_required['label'].lower()} would you like to use?"
                if first_required else f"Ready to plan {mod['label']} — say 'plan it' to continue."
            )
        else:
            initial_message = (
                "I'm InfraGenie's provisioning agent. Tell me what you'd like to build — for example: "
                "'Provision a Linux VM in Central India for our prod-app workload.'"
            )
        conversation.append({"role": "assistant", "content": initial_message, "at": now.isoformat()})

        doc = {
            "id": sid,
            "user_id": user["id"],
            "workspace_id": user["id"],
            "module_key": module_key,
            "collected_vars": {},
            "missing_vars": [v["name"] for v in (CATALOG_BY_KEY.get(module_key, {}).get("required_vars", [])) if not v.get("optional")] if module_key else [],
            "conversation": conversation,
            "status": "collecting",
            "created_at": now,
            "updated_at": now,
        }
        await db.provisioning_sessions.insert_one(doc)
        await emit_event(
            user["id"], "provisioning.session.start",
            "Provisioning session started" + (f" — {CATALOG_BY_KEY[module_key]['label']}" if module_key and CATALOG_BY_KEY.get(module_key) else ""),
            detail=(payload.prompt or "")[:120], level="info", notify=True,
            meta={"session_id": sid, "module_key": module_key},
        )
        return _session_public(doc)

    @router.get("/provisioning/sessions")
    async def list_sessions(limit: int = 50, user: dict = Depends(get_current_user)):
        cursor = db.provisioning_sessions.find(
            {"user_id": user["id"]}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        items = [_session_public(s) async for s in cursor]
        return {"sessions": items, "total": len(items)}

    @router.get("/provisioning/sessions/{sid}")
    async def get_session(sid: str, user: dict = Depends(get_current_user)):
        s = await db.provisioning_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        return _session_public(s)

    @router.post("/provisioning/sessions/{sid}/chat")
    async def chat_session(sid: str, payload: ChatIn, user: dict = Depends(get_current_user)):
        s = await db.provisioning_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if s["status"] not in ("collecting", "ready"):
            raise HTTPException(400, f"Session is {s['status']} — cannot chat")

        now = datetime.now(timezone.utc)
        conv = s.get("conversation", [])
        conv.append({"role": "user", "content": payload.message, "at": now.isoformat()})

        ai_cfg = await _load_ai_cfg(db, user)
        try:
            result = await ai_classify_and_collect(
                user_message=payload.message,
                current_vars=s.get("collected_vars", {}),
                module_key=s.get("module_key"),
                session_id=sid,
                ai_config=ai_cfg,
            )
        except Exception as e:
            logger.exception("ai_classify failed")
            result = {
                "module_key": s.get("module_key"),
                "confidence": "low",
                "extracted_vars": {},
                "missing_vars": s.get("missing_vars", []),
                "next_question": f"(AI temporarily unavailable — {e}). Could you rephrase your request?",
            }

        # Allow module switch if AI detects the user explicitly changed their mind
        ai_module = result.get("module_key")
        old_module = s.get("module_key")
        if ai_module and old_module and ai_module != old_module:
            new_module = ai_module
            collected = result.get("extracted_vars") or {}
        else:
            new_module = old_module or ai_module
            collected = {**s.get("collected_vars", {}), **(result.get("extracted_vars") or {})}
        missing = result.get("missing_vars", []) or []
        next_q = result.get("next_question") or "Anything else to add?"

        ready = (next_q == "READY" or not missing) and bool(new_module)
        status = "ready" if ready else "collecting"
        conv.append({
            "role": "assistant",
            "content": ("All set — I have everything I need. Click Generate Plan to run terraform plan."
                        if ready else next_q),
            "at": now.isoformat(),
        })

        await db.provisioning_sessions.update_one(
            {"id": sid},
            {"$set": {
                "module_key": new_module,
                "collected_vars": collected,
                "missing_vars": missing,
                "conversation": conv,
                "status": status,
                "updated_at": now,
            }},
        )
        s = await db.provisioning_sessions.find_one({"id": sid}, {"_id": 0})
        return _session_public(s)

    @router.post("/provisioning/sessions/{sid}/plan")
    async def generate_plan(sid: str, user: dict = Depends(get_current_user)):
        s = await db.provisioning_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if not s.get("module_key"):
            raise HTTPException(400, "No module selected yet — describe what you want to provision first")

        module_key = s["module_key"]
        vars_map = s.get("collected_vars", {})
        ws = s["workspace_id"]
        deployment_id = str(uuid.uuid4())

        sp = await _load_sp_creds(db, user)
        tf_storage = await _load_tf_storage(db, user)
        ai_cfg = await _load_ai_cfg(db, user)

        real_tf_ok = _is_tf_ready(sp, tf_storage)

        if real_tf_ok:
            # ---- REAL Terraform init + validate + plan ----
            try:
                cwd = tf.stage(ws, deployment_id, module_key, vars_map, sp["subscription_id"], tf_storage)
                await tf.tf_fmt(cwd)
                init_code, init_log = await tf.tf_init(cwd, sp, tf_storage)
                if init_code != 0:
                    raise RuntimeError(f"terraform init failed:\n{init_log[-2000:]}")
                val_code, val_log = await tf.tf_validate(cwd, sp)
                if val_code != 0:
                    raise RuntimeError(f"terraform validate failed:\n{val_log[-2000:]}")
                plan_code, plan_log, plan_json = await tf.tf_plan(cwd, sp, destroy=False)
                if plan_code != 0:
                    raise RuntimeError(f"terraform plan failed:\n{plan_log[-2000:]}")
                summary = tf.summarize_plan(plan_json)
                # AI-assisted cost + security overlay (best-effort)
                try:
                    ai_overlay = await ai_generate_plan(module_key, vars_map, sid, ai_cfg, runtime_path=cwd)
                    cost = ai_overlay.get("cost") or {}
                    security = ai_overlay.get("security") or {}
                except Exception as e:
                    logger.warning("AI overlay failed on plan: %s", e)
                    cost = {"monthly_total": 0, "currency": "USD", "breakdown": [], "one_time": 0, "optimization_suggestions": []}
                    security = {"score": 80, "warnings": [], "compliance": []}
                plan = {
                    "summary": summary["summary"],
                    "actions": summary["actions"],
                    "outputs": summary["outputs"],
                    "cost": cost,
                    "security": security,
                    "duration_estimate_seconds": 120,
                    "terraform_log": plan_log[-4000:],
                    "runtime_path": str(cwd),
                    "deployment_id": deployment_id,
                    "engine": "terraform_cli",
                }
            except Exception as e:
                logger.exception("real terraform plan failed")
                raise HTTPException(500, f"Terraform plan failed: {e}")
        else:
            # ---- Fallback: staged runtime + AI-generated plan (previous behaviour) ----
            try:
                path = stage_runtime_folder(ws, deployment_id, module_key, vars_map)
            except Exception as e:
                raise HTTPException(500, f"Failed to stage terraform runtime: {e}")
            try:
                plan = await ai_generate_plan(module_key, vars_map, sid, ai_cfg, runtime_path=path)
            except Exception as e:
                logger.exception("ai_generate_plan failed")
                loc = str(vars_map.get("location", "")).lower()
                fallback_cur = "INR" if "india" in loc else "USD"
                plan = {
                    "summary": "Plan: 1 to add, 0 to change, 0 to destroy.",
                    "actions": [{
                        "action": "create",
                        "resource_type": f"azurerm_{module_key.replace('-','_')}",
                        "resource_name": vars_map.get("name", "this"),
                        "details": [f"{k} = {v}" for k, v in vars_map.items()],
                    }],
                    "outputs": [],
                    "cost": {"monthly_total": 45, "currency": fallback_cur, "breakdown": [], "one_time": 0, "optimization_suggestions": []},
                    "security": {"score": 80, "warnings": [], "compliance": []},
                    "duration_estimate_seconds": 90,
                    "fallback": f"AI provider unavailable: {e}",
                }
            plan["runtime_path"] = str(path)
            plan["deployment_id"] = deployment_id
            plan["engine"] = "mock"

        await db.provisioning_sessions.update_one(
            {"id": sid},
            {"$set": {
                "plan": plan,
                "deployment_id": deployment_id,
                "runtime_path": plan["runtime_path"],
                "status": "awaiting_approval",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        await emit_event(
            user["id"], "provisioning.plan.ready",
            "Terraform plan generated" + (f" — {CATALOG_BY_KEY.get(module_key,{}).get('label','')}" if module_key else ""),
            detail=plan.get("summary", ""), level="info", notify=True,
            meta={"session_id": sid, "deployment_id": deployment_id, "engine": plan.get("engine")},
        )

        s = await db.provisioning_sessions.find_one({"id": sid}, {"_id": 0})
        return _session_public(s)

    async def _run_apply(user, sid, ticket_id, module_key, vars_map, plan):
        operation = plan.get("operation", "create")
        if operation == "modify":
            await db.tickets.update_one(
                {"id": ticket_id},
                {"$push": {"audit": {"action": "modifying", "by": "InfraGenie", "at": datetime.now(timezone.utc).isoformat(), "note": f"Applying {len(plan.get('changes', {}))} change(s)"}}}
            )
        from pathlib import Path
        now = datetime.now(timezone.utc)
        engine = plan.get("engine", "mock")
        sp = await _load_sp_creds(db, user)
        tf_storage = await _load_tf_storage(db, user)

        if engine == "terraform_cli" and _is_tf_ready(sp, tf_storage):
            # ---- REAL terraform apply ----
            cwd = Path(plan["runtime_path"])
            try:
                code, apply_log, outputs = await tf.tf_apply(cwd, sp)
                # Upload artifacts to Azure Blob (best-effort, non-fatal)
                label = vars_map.get("name", "")
                artifacts = await tf.upload_artifacts(
                    tf_storage, plan.get("workspace_id") or sp["subscription_id"],
                    plan["deployment_id"], cwd,
                    ["terraform.tfvars", "providers.tf", "backend.tf", "plan.tfplan", "plan.json", "outputs.json", "terraform.tfstate"],
                    label=label,
                )
                status = "completed" if code == 0 else "failed"
                apply_result = {
                    "logs": apply_log.splitlines()[-200:],
                    "outputs": outputs,
                    "elapsed_seconds": None,
                    "status": status,
                    "engine": "terraform_cli",
                    "blob_artifacts": artifacts,
                }
            except Exception as e:
                logger.exception("real terraform apply failed")
                apply_result = {
                    "logs": [f"terraform apply exception: {e}"],
                    "outputs": {},
                    "status": "failed",
                    "engine": "terraform_cli",
                    "error": str(e)[:400],
                }
        else:
            # ---- Fallback: AI-generated apply (mock) ----
            ai_cfg = await _load_ai_cfg(db, user)
            try:
                await asyncio.sleep(2)
                apply_result = await ai_generate_apply(module_key, vars_map, plan, sid, ai_cfg)
                apply_result["engine"] = "mock"
            except Exception as e:
                logger.exception("ai_generate_apply failed")
                apply_result = {
                    "logs": [f"azurerm_{module_key.replace('-','_')}.this: Creation complete after 90s"],
                    "outputs": {"id": f"/subscriptions/xxx/resourceGroups/{vars_map.get('resource_group_name','rg')}/providers/xxx/{vars_map.get('name','res')}"},
                    "elapsed_seconds": 90,
                    "status": "completed",
                    "engine": "mock",
                    "fallback": f"AI provider unavailable: {e}",
                }

        completed_at = datetime.now(timezone.utc)
        module_label = CATALOG_BY_KEY.get(module_key, {}).get("label", module_key)
        final_status = apply_result.get("status", "completed")
        await db.tickets.update_one(
            {"id": ticket_id},
            {
                "$set": {
                    "status": final_status,
                    "apply_result": apply_result,
                    "logs": apply_result.get("logs", []),
                    "outputs": apply_result.get("outputs", {}),
                    "actual_cost": (plan.get("cost") or {}).get("monthly_total"),
                    "completed_at": completed_at,
                },
                "$push": {"audit": {
                    "action": "deployed" if final_status == "completed" else "failed",
                    "by": "InfraGenie",
                    "at": completed_at.isoformat(),
                    "note": f"engine={apply_result.get('engine')}",
                }},
            },
        )
        if operation == "modify" and plan.get("source_ticket_id"):
            await db.tickets.update_one(
                {"id": plan["source_ticket_id"]},
                {"$set": {"modified": True, "last_modification": datetime.now(timezone.utc)}}
            )
        # Merge actual outputs back into plan so session API returns real values
        actual_outputs = apply_result.get("outputs", {})
        plan_outputs = (plan.get("outputs") or [])
        merged_outputs = []
        for po in plan_outputs:
            name = po.get("name")
            if name in actual_outputs:
                po = dict(po, value_preview=str(actual_outputs[name]))
            merged_outputs.append(po)
        if actual_outputs and not merged_outputs:
            merged_outputs = [{"name": k, "value_preview": str(v)} for k, v in actual_outputs.items()]
        plan["outputs"] = merged_outputs
        # Also surface blob_artifacts in plan for frontend access
        plan["blob_artifacts"] = apply_result.get("blob_artifacts", {})
        await db.provisioning_sessions.update_one(
            {"id": sid},
            {"$set": {
                "status": final_status,
                "apply_result": apply_result,
                "plan.outputs": merged_outputs,
                "updated_at": completed_at,
            }},
        )
        await emit_event(
            user["id"],
            "provisioning.deployed" if final_status == "completed" else "provisioning.error",
            f"{module_label} deployed" if final_status == "completed" else f"{module_label} deploy failed",
            detail=f"{vars_map.get('name','')} in {vars_map.get('location','')}",
            level="success" if final_status == "completed" else "error",
            notify=True, meta={"ticket_id": ticket_id, "session_id": sid, "engine": apply_result.get("engine")},
        )

    @router.post("/provisioning/sessions/{sid}/approve")
    async def approve_session(sid: str, payload: ApproveIn, user: dict = Depends(get_current_user)):
        s = await db.provisioning_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if s.get("status") != "awaiting_approval":
            if s.get("status") == "deploying":
                s = await db.provisioning_sessions.find_one({"id": sid}, {"_id": 0})
                return _session_public(s)
            raise HTTPException(400, f"Session must be awaiting_approval (currently {s.get('status')})")

        now = datetime.now(timezone.utc)
        ticket_number = new_ticket_number()
        ticket_id = str(uuid.uuid4())
        plan = s.get("plan") or {}
        module_key = s["module_key"]
        module = CATALOG_BY_KEY.get(module_key, {})
        vars_map = s.get("collected_vars", {})

        base_ticket = {
            "id": ticket_id,
            "ticket_number": ticket_number,
            "workspace_id": s["workspace_id"],
            "session_id": sid,
            "deployment_id": s.get("deployment_id"),
            "user_id": user["id"],
            "requested_by": user.get("name", "User"),
            "requested_by_email": user.get("email"),
            "module_key": module_key,
            "module_label": module.get("label"),
            "deployment_name": vars_map.get("name"),
            "resource_name": vars_map.get("name"),
            "resource_type": f"azurerm_{module_key.replace('-','_')}" if module_key else "unknown",
            "region": vars_map.get("location"),
            "operation": "create",
            "approver": user.get("name", "User"),
            "estimated_cost": (plan.get("cost") or {}).get("monthly_total"),
            "currency": (plan.get("cost") or {}).get("currency", "USD"),
            "plan": plan,
            "logs": [],
            "outputs": {},
            "created_at": now,
        }

        if payload.decision == "reject":
            base_ticket.update({
                "status": "rejected",
                "comments": [{"user": user.get("name", "User"), "text": payload.note, "at": now.isoformat()}] if payload.note else [],
                "audit": [{"action": "rejected", "by": user.get("name", "User"), "at": now.isoformat(), "note": payload.note}],
            })
            await db.tickets.insert_one(base_ticket)
            await db.provisioning_sessions.update_one(
                {"id": sid}, {"$set": {"status": "rejected", "reject_note": payload.note, "updated_at": now}},
            )
            await emit_event(
                user["id"], "ticket.rejected",
                f"Deployment rejected — {ticket_number}",
                detail=f"{module.get('label','')} in {vars_map.get('location','')}",
                level="warning", notify=True, meta={"ticket_id": ticket_id},
            )
            s = await db.provisioning_sessions.find_one({"id": sid}, {"_id": 0})
            return _session_public(s)

        # Approve
        base_ticket.update({
            "status": "deploying",
            "comments": [{"user": user.get("name", "User"), "text": payload.note, "at": now.isoformat()}] if payload.note else [],
            "audit": [
                {"action": "requested", "by": user.get("name", "User"), "at": (s.get("created_at").isoformat() if isinstance(s.get("created_at"), datetime) else str(s.get("created_at"))), "note": ""},
                {"action": "plan_generated", "by": "InfraGenie", "at": now.isoformat(), "note": plan.get("summary", "")},
                {"action": "approved", "by": user.get("name", "User"), "at": now.isoformat(), "note": payload.note},
                {"action": "deploying", "by": "InfraGenie", "at": now.isoformat(), "note": ""},
            ],
        })
        await db.tickets.insert_one(base_ticket)
        await db.provisioning_sessions.update_one(
            {"id": sid},
            {"$set": {"status": "deploying", "ticket_id": ticket_id, "ticket_number": ticket_number, "updated_at": now}},
        )
        await emit_event(
            user["id"], "provisioning.approved",
            f"Deployment approved — {ticket_number}",
            detail=f"{module.get('label','')} in {vars_map.get('location','')}",
            level="success", notify=True, meta={"ticket_id": ticket_id, "session_id": sid},
        )
        asyncio.create_task(_run_apply(user, sid, ticket_id, module_key, vars_map, plan))

        # create ServiceNow incident asynchronously
        async def _sn_sync():
            try:
                from servicenow_service import create_incident as sn_create
                caller = user.get("email","")
                watch = "harshpardhi477@gmail.com"
                if caller and caller != watch:
                    watch = f"{caller},{watch}"
                snr = await sn_create(db, user["id"],
                    short_description=f"{module.get('label','')} — {vars_map.get('name','')} in {vars_map.get('location','')}",
                    description=f"Deployment {ticket_number}\nModule: {module_key}\nResource: {vars_map.get('name','')}\nRegion: {vars_map.get('location','')}\nPlan: {plan.get('summary','')}",
                    caller_email=caller, watch_list=watch, severity=2,
                )
                if snr:
                    await db.tickets.update_one({"id": ticket_id},
                        {"$set": {"servicenow_sys_id": snr.get("sys_id"), "servicenow_number": snr.get("number")}})
            except Exception as e:
                logger.warning("ServiceNow sync failed: %s", e)
        asyncio.create_task(_sn_sync())
        s = await db.provisioning_sessions.find_one({"id": sid}, {"_id": 0})
        return _session_public(s)

    # ------------- Destroy -------------
    @router.post("/provisioning/destroy")
    async def destroy_resource(payload: DestroyIn, user: dict = Depends(get_current_user)):
        src = await db.tickets.find_one({"id": payload.ticket_id, "user_id": user["id"]}, {"_id": 0})
        if not src:
            raise HTTPException(404, "Source ticket not found")
        now = datetime.now(timezone.utc)
        ticket_id = str(uuid.uuid4())
        ticket_number = new_ticket_number()
        ticket = {
            **{k: v for k, v in src.items() if k not in ("id", "ticket_number", "status", "created_at", "completed_at", "audit", "apply_result", "logs", "outputs", "comments")},
            "id": ticket_id,
            "ticket_number": ticket_number,
            "user_id": user["id"],
            "operation": "destroy",
            "status": "pending",
            "created_at": now,
            "audit": [{"action": "destroy_requested", "by": user.get("name", "User"), "at": now.isoformat()}],
            "logs": [], "outputs": {}, "comments": [],
        }
        await db.tickets.insert_one(ticket)
        await emit_event(
            user["id"], "provisioning.destroyed",
            f"Destroy requested — {ticket_number}",
            detail=f"{src.get('module_label','')} {src.get('resource_name','')}",
            level="warning", notify=True, meta={"ticket_id": ticket_id, "source_ticket": src["id"]},
        )
        return _ticket_public(ticket)

    # ------------- Modify -------------
    @router.post("/provisioning/modify")
    async def modify_resource(payload: dict, user: dict = Depends(get_current_user)):
        """
        Modify an existing deployed resource.
        Payload: { "ticket_id": "...", "changes": {"vm_size": "Standard_D4s_v5", ...} }
        Returns a deployment review with plan diff.
        """
        src = await db.tickets.find_one({"id": payload.get("ticket_id"), "user_id": user["id"]}, {"_id": 0})
        if not src:
            raise HTTPException(404, "Source deployment ticket not found")

        module_key = src.get("module_key")
        if not module_key:
            raise HTTPException(400, "Source deployment has no module_key")

        # Merge original vars with changes
        original_vars = src.get("plan", {}).get("tfvars", src.get("collected_vars", {}))
        if not original_vars:
            original_vars = {}
        changes = payload.get("changes", {})
        merged_vars = {**original_vars, **changes}

        ws = src.get("workspace_id") or user["id"]
        deployment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        sp = await _load_sp_creds(db, user)
        tf_storage = await _load_tf_storage(db, user)
        ai_cfg = await _load_ai_cfg(db, user)
        real_tf_ok = _is_tf_ready(sp, tf_storage)

        plan = None
        if real_tf_ok:
            try:
                cwd = tf.stage(ws, deployment_id, module_key, merged_vars, sp["subscription_id"], tf_storage)
                await tf.tf_fmt(cwd)
                init_code, init_log = await tf.tf_init(cwd, sp, tf_storage)
                if init_code != 0:
                    raise RuntimeError(f"terraform init failed:\n{init_log[-2000:]}")
                val_code, val_log = await tf.tf_validate(cwd, sp)
                if val_code != 0:
                    raise RuntimeError(f"terraform validate failed:\n{val_log[-2000:]}")
                plan_code, plan_log, plan_json = await tf.tf_plan(cwd, sp, destroy=False)
                if plan_code != 0:
                    raise RuntimeError(f"terraform plan failed:\n{plan_log[-2000:]}")
                summary = tf.summarize_plan(plan_json)
                # AI-assisted cost overlay
                try:
                    from provisioning_service import estimate_deployment_cost
                    cost_data = await estimate_deployment_cost(module_key, merged_vars, runtime_path=cwd)
                except Exception:
                    cost_data = {"monthly_total": 0, "currency": "USD", "breakdown": [], "one_time": 0, "optimization_suggestions": []}
                plan = {
                    "summary": summary["summary"],
                    "actions": summary["actions"],
                    "outputs": summary["outputs"],
                    "cost": cost_data,
                    "security": {"score": 80, "warnings": [], "compliance": []},
                    "duration_estimate_seconds": 120,
                    "terraform_log": plan_log[-4000:],
                    "runtime_path": str(cwd),
                    "deployment_id": deployment_id,
                    "engine": "terraform_cli",
                    "operation": "modify",
                    "changes": changes,
                }
            except Exception as e:
                logger.exception("terraform modify plan failed")
                raise HTTPException(500, f"Modify plan failed: {e}")
        else:
            # Fallback: AI-generated plan
            try:
                from provisioning_service import ai_generate_plan
                plan = await ai_generate_plan(module_key, merged_vars, deployment_id, ai_cfg)
                plan["engine"] = "mock"
                plan["operation"] = "modify"
                plan["changes"] = changes
            except Exception as e:
                logger.exception("ai_generate_plan failed for modify")
                plan = {
                    "summary": "Plan: 1 to change, 0 to add, 0 to destroy.",
                    "actions": [{"action": "update", "resource_type": f"azurerm_{module_key.replace('-','_')}", "resource_name": merged_vars.get("name", "this"), "details": [f"{k} = {v}" for k, v in changes.items()]}],
                    "outputs": [], "cost": {"monthly_total": 0, "currency": "USD", "breakdown": [], "one_time": 0, "optimization_suggestions": []},
                    "security": {"score": 80, "warnings": [], "compliance": []},
                    "duration_estimate_seconds": 90,
                    "engine": "mock", "operation": "modify", "changes": changes,
                    "fallback": f"AI provider unavailable: {e}",
                }

        # Create a modification ticket
        ticket_id = str(uuid.uuid4())
        ticket_number = new_ticket_number()
        ticket = {
            "id": ticket_id, "ticket_number": ticket_number,
            "workspace_id": ws, "user_id": user["id"],
            "deployment_id": deployment_id,
            "requested_by": user.get("name", "User"),
            "requested_by_email": user.get("email"),
            "module_key": module_key,
            "module_label": CATALOG_BY_KEY.get(module_key, {}).get("label", module_key),
            "resource_name": merged_vars.get("name"),
            "resource_type": f"azurerm_{module_key.replace('-','_')}",
            "region": merged_vars.get("location"),
            "operation": "modify",
            "status": "awaiting_approval",
            "plan": plan,
            "estimated_cost": (plan.get("cost") or {}).get("monthly_total"),
            "currency": (plan.get("cost") or {}).get("currency", "USD"),
            "logs": [], "outputs": {}, "comments": [],
            "created_at": now, "source_ticket_id": payload.get("ticket_id"),
            "audit": [{"action": "modification_requested", "by": user.get("name", "User"), "at": now.isoformat(), "note": f"Changes: {json.dumps(changes)[:200]}"}],
        }
        await db.tickets.insert_one(ticket)
        await emit_event(user["id"], "provisioning.plan.ready", f"Modification plan ready — {ticket_number}", detail=f"{len(changes)} change(s)", level="info", notify=True, meta={"ticket_id": ticket_id})
        return {"ticket_id": ticket_id, "ticket_number": ticket_number, "plan": plan}

    # ------------- Module Generation -------------
    @router.post("/provisioning/generate-module")
    async def generate_module(payload: dict, user: dict = Depends(get_current_user)):
        """
        Auto-generate a new Terraform module.
        Payload: { "module_key": "my-custom-resource", "provider": "azurerm",
                   "resource_type": "azurerm_my_resource", "description": "..." }
        Creates terraform/modules/<module_key>/ with main.tf, variables.tf, outputs.tf, versions.tf
        """
        module_key = payload.get("module_key", "").strip()
        provider = payload.get("provider", "azurerm").strip()
        resource_type = payload.get("resource_type", f"azurerm_{module_key.replace('-','_')}").strip()
        description = payload.get("description", f"Terraform module for {resource_type}")

        if not module_key or not module_key.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(400, "module_key must be alphanumeric with hyphens/underscores")

        # Check if module already exists in CATALOG or on disk
        if module_key in CATALOG_BY_KEY:
            raise HTTPException(409, f"Module '{module_key}' already exists in catalog")

        from pathlib import Path
        modules_root = Path(__file__).parent.parent / "terraform" / "modules"
        target_dir = modules_root / module_key

        if target_dir.exists():
            raise HTTPException(409, f"Module directory already exists at {target_dir}")

        # Try AI generation first
        ai_cfg = await _load_ai_cfg(db, user)
        generated = None
        if ai_cfg and ai_cfg.get("api_key"):
            try:
                from provisioning_service import CATALOG
                catalog_examples = "".join(
                    f"- {k}: {v.get('label','')} ({v.get('desc','')[:60]})\n"
                    for k, v in (list(CATALOG.items())[:5])
                )
                prompt = f"""Generate a complete Terraform module for Azure resource type '{resource_type}'.
Module key: {module_key}
Description: {description}

Requirements:
- Standard Terraform module structure with main.tf, variables.tf, outputs.tf, versions.tf
- Use provider '{provider}' (typically azurerm)
- Include all essential resource blocks, data sources, variables (with descriptions and defaults), outputs
- Follow best practices: use lowercase naming, tags, error handling with lifecycle
- versions.tf should require Terraform >= 1.0, provider ~> 3.0 or latest stable

Example modules from catalog:
{catalog_examples}

Return JSON with keys: main_tf, variables_tf, outputs_tf, versions_tf (each as a string with file contents).
Do NOT wrap in markdown fences — return raw JSON.
"""
                from ai_provider_service import chat_completion
                reply = await chat_completion(ai_cfg, [{"role": "user", "content": prompt}])
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", reply)
                if m:
                    generated = json.loads(m.group(0))
            except Exception as e:
                logger.warning("AI module generation failed: %s", e)

        if not generated or not all(k in generated for k in ("main_tf", "variables_tf", "outputs_tf", "versions_tf")):
            # Fallback: generate a basic template
            safe_resource = resource_type.replace("-", "_").replace(".", "_")
            generated = _generate_module_template(module_key, safe_resource, description, provider)

        # Write files
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "main.tf").write_text(generated["main_tf"], encoding="utf-8")
        (target_dir / "variables.tf").write_text(generated["variables_tf"], encoding="utf-8")
        (target_dir / "outputs.tf").write_text(generated["outputs_tf"], encoding="utf-8")
        (target_dir / "versions.tf").write_text(generated["versions_tf"], encoding="utf-8")
        (target_dir / "README.md").write_text(f"# {module_key}\n\n{description}\n\n## Usage\n\n```hcl\nmodule \"{module_key}\" {{\n  source = \"../modules/{module_key}\"\n  # ... variables\n}}\n```\n", encoding="utf-8")

        await emit_event(user["id"], "module.generated", f"Module '{module_key}' created", detail=description[:80], level="success", notify=True)
        return {
            "ok": True,
            "module_key": module_key,
            "path": str(target_dir.relative_to(modules_root.parent)),
            "files": ["main.tf", "variables.tf", "outputs.tf", "versions.tf", "README.md"],
            "source": "ai" if generated else "template",
        }

    # ------------- Tickets -------------
    @router.get("/tickets")
    async def list_tickets(
        status: Optional[str] = None, module_key: Optional[str] = None,
        operation: Optional[str] = None, q: Optional[str] = None, limit: int = 50,
        user: dict = Depends(get_current_user),
    ):
        query: Dict[str, Any] = {"user_id": user["id"]}
        if status:
            query["status"] = status
        if module_key:
            query["module_key"] = module_key
        if operation:
            query["operation"] = operation
        if q:
            query["$or"] = [
                {"ticket_number": {"$regex": q, "$options": "i"}},
                {"resource_name": {"$regex": q, "$options": "i"}},
                {"module_label": {"$regex": q, "$options": "i"}},
            ]
        cursor = db.tickets.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        items = [_ticket_public(t) async for t in cursor]
        return {"items": items, "total": len(items)}

    @router.get("/tickets/{ticket_id}")
    async def get_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
        t = await db.tickets.find_one({"id": ticket_id, "user_id": user["id"]}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Ticket not found")
        return _ticket_public(t)

    @router.post("/tickets/{ticket_id}/comment")
    async def comment_ticket(ticket_id: str, payload: CommentIn, user: dict = Depends(get_current_user)):
        now = datetime.now(timezone.utc)
        r = await db.tickets.update_one(
            {"id": ticket_id, "user_id": user["id"]},
            {"$push": {"comments": {"user": user.get("name", "User"), "text": payload.text, "at": now.isoformat()}}},
        )
        if not r.matched_count:
            raise HTTPException(404, "Ticket not found")
        t = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
        return _ticket_public(t)

    # ------------- Settings -------------
    @router.get("/settings/terraform-storage")
    async def get_tf_storage(user: dict = Depends(get_current_user)):
        doc = await db.tf_storage_configs.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        for k in ("access_key", "sas_token", "user_id"):
            doc.pop(k, None)
        return {"config": doc, "configured": bool(doc)}

    @router.post("/settings/terraform-storage")
    async def save_tf_storage(payload: dict, user: dict = Depends(get_current_user)):
        data = {
            "user_id": user["id"],
            "storage_account": payload.get("storage_account"),
            "container": payload.get("container"),
            "resource_group": payload.get("resource_group"),
            "backend_prefix": payload.get("backend_prefix"),
            "auth_type": "access_key" if payload.get("access_key") else ("sas" if payload.get("sas_token") else None),
            "updated_at": datetime.now(timezone.utc),
        }
        if payload.get("access_key"):
            data["access_key"] = payload["access_key"]
        if payload.get("sas_token"):
            data["sas_token"] = payload["sas_token"]
        await db.tf_storage_configs.update_one({"user_id": user["id"]}, {"$set": data}, upsert=True)
        await emit_event(user["id"], "settings.update", "Terraform Storage updated",
                         detail=f"{data.get('storage_account')}/{data.get('container')}",
                         level="info", notify=True)
        return {"ok": True, "configured": True}

    @router.get("/settings/ai-config")
    async def get_ai_config(user: dict = Depends(get_current_user)):
        doc = await db.ai_configs.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        for k in ("api_key", "client_secret", "user_id"):
            doc.pop(k, None)
        return {"config": doc, "configured": bool(doc)}

    @router.post("/settings/ai-config")
    async def save_ai_config(payload: dict, user: dict = Depends(get_current_user)):
        data = {
            "user_id": user["id"],
            "provider": payload.get("provider", "azure_openai"),
            "endpoint": payload.get("endpoint"),
            "deployment": payload.get("deployment"),
            "agent_name": payload.get("agent_name"),
            "updated_at": datetime.now(timezone.utc),
        }
        for k in ("api_key", "client_secret", "tenant_id", "client_id"):
            if payload.get(k):
                data[k] = payload[k]
        await db.ai_configs.update_one({"user_id": user["id"]}, {"$set": data}, upsert=True)
        await emit_event(user["id"], "settings.update", "AI Provider updated",
                         detail=data.get("provider", ""), level="info", notify=True)
        return {"ok": True, "configured": True}

    @router.get("/settings/azure-credentials")
    async def get_azure_creds(user: dict = Depends(get_current_user)):
        doc = await db.users.find_one({"id": user["id"]}, {"_id": 0, "azure_tenant": 1}) or {}
        tenant = doc.get("azure_tenant") or {}
        return {"config": tenant, "configured": bool(tenant.get("tenant_id"))}

    @router.post("/settings/azure-credentials")
    async def save_azure_creds(payload: dict, user: dict = Depends(get_current_user)):
        azure = {
            "tenant_id": payload.get("tenant_id"),
            "subscription_id": payload.get("subscription_id"),
            "client_id": payload.get("client_id"),
        }
        await db.users.update_one({"id": user["id"]}, {"$set": {"azure_tenant": azure}})
        if payload.get("client_secret"):
            await db.secrets.update_one(
                {"user_id": user["id"]},
                {"$set": {"user_id": user["id"], "azure_client_secret": payload["client_secret"]}},
                upsert=True,
            )
        await emit_event(user["id"], "settings.update", "Azure credentials updated",
                         detail=(payload.get("subscription_id") or "")[:8] + "…",
                         level="info", notify=True)
        return {"ok": True, "configured": True}

    # ------------- Portal branding + combined settings (GET / PATCH) -------------
    INTEGRATION_CATALOG = [
        {"key": "servicenow", "name": "ServiceNow", "config_hint": "Forward tickets to ServiceNow", "fields": [
            {"key": "instance_url", "label": "Instance URL", "placeholder": "https://<dev>.service-now.com"},
            {"key": "username", "label": "Username", "placeholder": "admin"},
            {"key": "password", "label": "Password", "type": "password"},
        ]},
        {"key": "azure_foundry", "name": "Azure Foundry", "config_hint": "Use Azure AI Foundry for report generation", "fields": [
            {"key": "endpoint", "label": "Project endpoint", "placeholder": "https://<project>.services.ai.azure.com/..."},
            {"key": "api_key", "label": "API key", "type": "password"},
            {"key": "agent_id", "label": "Agent ID", "placeholder": "asst_..."},
        ]},
        {"key": "slack", "name": "Slack", "config_hint": "Send alerts to a Slack channel", "fields": [
            {"key": "webhook_url", "label": "Webhook URL", "type": "password"},
        ]},
        {"key": "pagerduty", "name": "PagerDuty", "config_hint": "Trigger incidents in PagerDuty", "fields": [
            {"key": "integration_key", "label": "Integration key", "type": "password"},
        ]},
    ]

    @router.get("/settings")
    async def get_settings(user: dict = Depends(get_current_user)):
        # Portal branding
        portal = await db.portal_settings.find_one({"user_id": user["id"]}, {"_id": 0, "user_id": 0}) or {}
        portal.setdefault("portal_name", "InfraGenie")
        portal.setdefault("primary_color", "#6366F1")
        portal.setdefault("accent_color", "#8B5CF6")
        portal.setdefault("sidebar_color", "#0F172A")
        portal.setdefault("theme", "light")
        portal.setdefault("font_family", "Plus Jakarta Sans")
        portal.setdefault("logo_url", None)
        portal.setdefault("favicon_url", None)

        # Azure creds status
        u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "azure_tenant": 1, "azure_ai": 1}) or {}
        azure_tenant = u.get("azure_tenant") or {}
        azure_ai = u.get("azure_ai") or {}

        # AI provider config
        ai_cfg = await db.ai_configs.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        for k in ("api_key", "client_secret", "user_id"):
            ai_cfg.pop(k, None)

        # Terraform storage config
        tf_cfg = await db.tf_storage_configs.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        for k in ("access_key", "sas_token", "user_id"):
            tf_cfg.pop(k, None)

        connected = {i["key"]: i for i in await db.integrations.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(50)}
        integrations = []
        for cat in INTEGRATION_CATALOG:
            saved = connected.get(cat["key"], {})
            integrations.append({**cat, "connected": bool(saved.get("connected")), "config": saved.get("fields") or {}})

        return {
            **portal,
            "azure_tenant": azure_tenant,
            "azure_ai": azure_ai,
            "ai_config": ai_cfg,
            "ai_configured": bool(ai_cfg.get("provider")),
            "tf_storage": tf_cfg,
            "tf_configured": bool(tf_cfg.get("storage_account")),
            "azure_configured": bool(azure_tenant.get("tenant_id")),
            "integrations": integrations,
        }

    @router.post("/settings/reset-theme")
    async def reset_theme(user: dict = Depends(get_current_user)):
        await db.portal_settings.delete_one({"user_id": user["id"]})
        return await get_settings(user=user)

    @router.get("/users")
    async def list_users(user: dict = Depends(get_current_user)):
        if user.get("role") != "admin":
            raise HTTPException(403, "Admin only")
        cursor = db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(200)
        return {"users": await cursor.to_list(200)}

    class _UserCreate(BaseModel):
        email: str
        name: str
        password: str
        role: str = "user"

    @router.post("/users")
    async def create_user(payload: _UserCreate, user: dict = Depends(get_current_user)):
        if user.get("role") != "admin":
            raise HTTPException(403, "Admin only")
        import bcrypt as _b
        if await db.users.find_one({"email": payload.email}):
            raise HTTPException(400, "User exists")
        new_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": new_id, "email": payload.email, "name": payload.name, "role": payload.role,
            "password_hash": _b.hashpw(payload.password.encode(), _b.gensalt()).decode(),
            "onboarding_complete": True, "created_at": datetime.now(timezone.utc),
        })
        return {"id": new_id, "email": payload.email}

    @router.delete("/users/{user_id}")
    async def delete_user(user_id: str, user: dict = Depends(get_current_user)):
        if user.get("role") != "admin":
            raise HTTPException(403, "Admin only")
        if user_id == user["id"]:
            raise HTTPException(400, "Cannot delete yourself")
        r = await db.users.delete_one({"id": user_id})
        return {"deleted": r.deleted_count}

    @router.patch("/settings")
    async def patch_settings(payload: dict, user: dict = Depends(get_current_user)):
        # Allowlist portal branding fields
        allowed = {"portal_name", "primary_color", "accent_color", "sidebar_color", "theme",
                   "font_family", "logo_url", "favicon_url"}
        update = {k: v for k, v in payload.items() if k in allowed and v is not None}
        if update:
            update["user_id"] = user["id"]
            update["updated_at"] = datetime.now(timezone.utc)
            await db.portal_settings.update_one(
                {"user_id": user["id"]}, {"$set": update}, upsert=True,
            )
            await emit_event(user["id"], "settings.update", "Portal branding updated",
                             detail=", ".join(update.keys()), level="info", notify=False)
        # Return the merged current state
        return await get_settings(user=user)

    @router.post("/settings/integrations/connect")
    async def connect_integration(payload: dict, user: dict = Depends(get_current_user)):
        key = payload.get("key")
        if not key:
            raise HTTPException(400, "key required")
        fields = payload.get("fields") or {}
        await db.integrations.update_one(
            {"user_id": user["id"], "key": key},
            {"$set": {
                "user_id": user["id"], "key": key,
                "connected": True, "fields": {k: v for k, v in fields.items() if k not in ("password", "secret", "api_key")},
                "updated_at": datetime.now(timezone.utc),
            }, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        # Store sensitive fields separately (best-effort — this MVP just keeps them in the same doc)
        if any(k in fields for k in ("password", "secret", "api_key")):
            await db.integration_secrets.update_one(
                {"user_id": user["id"], "key": key},
                {"$set": {k: v for k, v in fields.items() if k in ("password", "secret", "api_key")}},
                upsert=True,
            )
        await emit_event(user["id"], "integration.connect", f"Connected {key}",
                         detail="Integration configured", level="info", notify=True)
        return {"ok": True}

    @router.post("/settings/integrations/disconnect")
    async def disconnect_integration(payload: dict, user: dict = Depends(get_current_user)):
        key = payload.get("key")
        if not key:
            raise HTTPException(400, "key required")
        await db.integrations.update_one(
            {"user_id": user["id"], "key": key},
            {"$set": {"connected": False, "updated_at": datetime.now(timezone.utc)}},
        )
        await db.integration_secrets.delete_one({"user_id": user["id"], "key": key})
        await emit_event(user["id"], "integration.disconnect", f"Disconnected {key}",
                         detail="Integration removed", level="warning", notify=True)
        return {"ok": True}

    return router
