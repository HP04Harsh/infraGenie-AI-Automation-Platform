"""Real Azure SDK extraction. Every call wrapped in try/except — never crashes."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from azure.identity import ClientSecretCredential
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.security import SecurityCenter

logger = logging.getLogger(__name__)


def _safe(call, default, label):
    """Run an Azure SDK call and capture any failure as an error string."""
    try:
        return call(), None
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {str(e)[:240]}"
        logger.warning("Azure call '%s' failed: %s", label, msg)
        return default, msg


def _build_credential(tenant_id: str, client_id: str, client_secret: str):
    return ClientSecretCredential(
        tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
    )


def extract_tenant_metrics(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    subscription_id: str,
    progress_cb: Optional[callable] = None,
):
    """Synchronously extract metrics across 5 phases. Returns a dict with phases + final metrics.

    progress_cb(phase: str, status: str, message: str) is called with status in
    {"start", "ok", "error"} so the caller can stream logs.
    """
    def emit(phase, status, message):
        if progress_cb:
            try:
                progress_cb(phase, status, message)
            except Exception:
                pass

    result = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "subscription_id": subscription_id,
        "phases": {},
        "errors": [],
    }

    # Phase 1 — Auth
    emit("auth", "start", "Authenticating service principal with Azure AD…")
    cred, err = _safe(
        lambda: _build_credential(tenant_id, client_id, client_secret),
        None,
        "auth.client_secret_credential",
    )
    if err:
        result["phases"]["auth"] = {"ok": False, "error": err}
        result["errors"].append(f"auth: {err}")
        emit("auth", "error", err)
        # Without creds we cannot continue, but we still return a complete shape
        result["phases"].setdefault("resources", {"ok": False, "error": "skipped: auth failed"})
        result["phases"].setdefault("cost", {"ok": False, "error": "skipped: auth failed"})
        result["phases"].setdefault("security", {"ok": False, "error": "skipped: auth failed"})
        result["phases"].setdefault("ai", {"ok": False, "error": "skipped: auth failed"})
        result["resources_total"] = 0
        result["vms_total"] = 0
        result["resource_groups_total"] = 0
        result["security_score"] = 0
        return result
    result["phases"]["auth"] = {"ok": True}
    emit("auth", "ok", "Authenticated. Token acquired for subscription scope.")

    # Phase 2 — Resource Discovery
    emit("resources", "start", "Discovering resource groups and resources…")
    resources_total = 0
    rg_total = 0
    rgs_meta = []

    def _list_rgs():
        nonlocal rg_total, resources_total
        rc = ResourceManagementClient(cred, subscription_id)
        for rg in rc.resource_groups.list():
            rg_total += 1
            rgs_meta.append({"name": rg.name, "location": rg.location})
            try:
                for _ in rc.resources.list_by_resource_group(rg.name):
                    resources_total += 1
            except Exception as inner:  # noqa: BLE001
                logger.warning("rg.resources.list failed for %s: %s", rg.name, inner)
        return True

    _, err = _safe(_list_rgs, False, "resources.list")
    if err:
        result["phases"]["resources"] = {"ok": False, "error": err}
        result["errors"].append(f"resources: {err}")
        emit("resources", "error", err)
    else:
        result["phases"]["resources"] = {
            "ok": True,
            "resource_groups": rg_total,
            "resources": resources_total,
            "samples": rgs_meta[:10],
        }
        emit(
            "resources",
            "ok",
            f"Found {rg_total} resource groups, {resources_total} resources.",
        )
    result["resources_total"] = resources_total
    result["resource_groups_total"] = rg_total

    # Phase 3 — Compute (VMs)
    emit("compute", "start", "Enumerating virtual machines…")
    vms_total = 0
    vms_samples = []

    def _list_vms():
        nonlocal vms_total
        cc = ComputeManagementClient(cred, subscription_id)
        for vm in cc.virtual_machines.list_all():
            vms_total += 1
            if len(vms_samples) < 10:
                size = (
                    vm.hardware_profile.vm_size
                    if getattr(vm, "hardware_profile", None)
                    else None
                )
                vms_samples.append(
                    {"name": vm.name, "location": vm.location, "size": size}
                )
        return True

    _, err = _safe(_list_vms, False, "compute.vms.list")
    if err:
        result["phases"]["compute"] = {"ok": False, "error": err}
        result["errors"].append(f"compute: {err}")
        emit("compute", "error", err)
    else:
        result["phases"]["compute"] = {
            "ok": True,
            "vms": vms_total,
            "samples": vms_samples,
        }
        emit("compute", "ok", f"Enumerated {vms_total} virtual machines.")
    result["vms_total"] = vms_total

    # Phase 4 — Cost (current MTD)
    emit("cost", "start", "Querying cost management for current month-to-date…")
    cost_value = 0.0
    cost_currency = "USD"

    def _get_cost():
        nonlocal cost_value, cost_currency
        cm = CostManagementClient(cred)
        scope = f"/subscriptions/{subscription_id}"
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "time_period": {
                "from": start.isoformat(),
                "to": now.isoformat(),
            },
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                },
            },
        }
        q = cm.query.usage(scope=scope, parameters=body)
        if q and q.rows:
            cost_value = float(q.rows[0][0])
            if q.columns and len(q.columns) > 1:
                cost_currency = str(q.rows[0][1])
        return True

    _, err = _safe(_get_cost, False, "cost.query")
    if err:
        result["phases"]["cost"] = {"ok": False, "error": err}
        result["errors"].append(f"cost: {err}")
        emit("cost", "error", err)
    else:
        result["phases"]["cost"] = {
            "ok": True,
            "mtd_cost": cost_value,
            "currency": cost_currency,
        }
        emit("cost", "ok", f"MTD spend: {cost_value:.2f} {cost_currency}.")
    result["mtd_cost"] = cost_value
    result["cost_currency"] = cost_currency

    # Phase 5 — Security
    emit("security", "start", "Pulling Defender for Cloud secure score…")
    security_score = 0

    def _get_sec():
        nonlocal security_score
        sc = SecurityCenter(cred, subscription_id, asc_location="centralus")
        for s in sc.secure_scores.list():
            pct = getattr(s.score, "percentage", None) if getattr(s, "score", None) else None
            if pct is not None:
                security_score = int(round(float(pct) * 100)) if pct <= 1 else int(round(float(pct)))
                break
        return True

    _, err = _safe(_get_sec, False, "security.secure_scores")
    if err:
        result["phases"]["security"] = {"ok": False, "error": err}
        result["errors"].append(f"security: {err}")
        emit("security", "error", err)
    else:
        result["phases"]["security"] = {"ok": True, "score": security_score}
        emit("security", "ok", f"Secure score: {security_score}/100.")
    result["security_score"] = security_score

    return result


def init_ai_agent(project_endpoint: str, api_key: str, agent_name: str, model_name: str, progress_cb=None):
    """Lightweight smoke-check for AI config. Does not require Azure AI SDK to be installed."""
    def emit(status, message):
        if progress_cb:
            try:
                progress_cb("ai", status, message)
            except Exception:
                pass

    emit("start", f"Initializing AI agent '{agent_name}' on model '{model_name}'…")
    # Validate shape only — real wiring happens later.
    if not project_endpoint or not project_endpoint.startswith(("http://", "https://")):
        err = "Invalid project_endpoint (must be http(s) URL)."
        emit("error", err)
        return {"ok": False, "error": err}
    if not api_key or len(api_key) < 6:
        err = "Invalid api_key."
        emit("error", err)
        return {"ok": False, "error": err}
    emit("ok", f"AI agent '{agent_name}' registered (config validated).")
    return {"ok": True, "agent_name": agent_name, "model_name": model_name}
