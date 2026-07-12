"""InfraGenie Tenant AI Bridge.

Wraps Azure OpenAI with function-calling tools that query the user's real Azure tenant
via the Service Principal stored in Settings. Any InfraGenie chat surface (dashboard
Smart Assist, Optimization / Troubleshoot / Compliance / Support / Reports / Observability
Ask-the-Agent inputs) should call `tenant_chat()` — never call OpenAI directly.

Contract:
    result = await tenant_chat(db, user, messages, hint=None, extra_tools=None)
    # result = {"reply": str, "tool_traces": [...], "provider": "azure_openai" | "openai_fallback"}
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ai_provider_service import load_user_config

logger = logging.getLogger("tenant_ai")


# ---------- Tenant tool implementations (each returns JSON-serialisable dict) ----------

def _sp_cred(sp: Dict[str, str]):
    from azure.identity import ClientSecretCredential
    return ClientSecretCredential(
        tenant_id=sp["tenant_id"], client_id=sp["client_id"], client_secret=sp["client_secret"]
    )


async def _run_blocking(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def _tool_list_resource_groups(sp: Dict[str, str]) -> Dict[str, Any]:
    from azure.mgmt.resource.resources import ResourceManagementClient
    cred = _sp_cred(sp)
    rc = ResourceManagementClient(cred, sp["subscription_id"])
    items = [{"name": rg.name, "location": rg.location, "id": rg.id} for rg in rc.resource_groups.list()]
    return {"count": len(items), "resource_groups": items}


def _tool_list_resources(sp: Dict[str, str], resource_group: Optional[str] = None, resource_type: Optional[str] = None, top: int = 200) -> Dict[str, Any]:
    from azure.mgmt.resource.resources import ResourceManagementClient
    cred = _sp_cred(sp)
    rc = ResourceManagementClient(cred, sp["subscription_id"])
    items = []
    it = rc.resources.list_by_resource_group(resource_group) if resource_group else rc.resources.list()
    for r in it:
        if resource_type and (r.type or "").lower() != resource_type.lower():
            continue
        items.append({"name": r.name, "type": r.type, "location": r.location, "id": r.id, "tags": r.tags or {}})
        if len(items) >= top:
            break
    return {"count": len(items), "resources": items}


def _tool_list_vms(sp: Dict[str, str]) -> Dict[str, Any]:
    from azure.mgmt.compute import ComputeManagementClient
    cred = _sp_cred(sp)
    cc = ComputeManagementClient(cred, sp["subscription_id"])
    items = []
    for vm in cc.virtual_machines.list_all():
        items.append({
            "name": vm.name,
            "location": vm.location,
            "size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
            "os": (vm.storage_profile.os_disk.os_type if vm.storage_profile and vm.storage_profile.os_disk else None),
            "id": vm.id,
        })
    return {"count": len(items), "vms": items}


def _tool_get_costs(sp: Dict[str, str], scope: str = "mtd", top_n_by_resource: int = 0) -> Dict[str, Any]:
    from azure.mgmt.costmanagement import CostManagementClient
    cred = _sp_cred(sp)
    cm = CostManagementClient(cred)
    subscription_scope = f"/subscriptions/{sp['subscription_id']}"
    now = datetime.now(timezone.utc)
    if scope == "mtd":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if top_n_by_resource > 0:
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "time_period": {"from": start.isoformat(), "to": now.isoformat()},
            "dataset": {
                "granularity": "None",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": [{"type": "Dimension", "name": "ResourceId"}],
                "sorting": [{"direction": "descending", "name": "Cost"}],
            },
        }
        q = cm.query.usage(scope=subscription_scope, parameters=body)
        rows = []
        for row in (q.rows or [])[:top_n_by_resource]:
            rows.append({"cost": float(row[0]), "resource_id": row[1] if len(row) > 1 else None})
        total = sum(r["cost"] for r in rows)
        return {"scope": "mtd", "currency": "INR", "total": round(total, 2), "top_resources": rows}
    else:
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "time_period": {"from": start.isoformat(), "to": now.isoformat()},
            "dataset": {"granularity": "None", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}}},
        }
        q = cm.query.usage(scope=subscription_scope, parameters=body)
        total = float(q.rows[0][0]) if q and q.rows else 0.0
        currency = str(q.rows[0][1]) if q and q.rows and q.columns and len(q.columns) > 1 else "INR"
        return {"scope": "mtd", "total": round(total, 2), "currency": currency}


def _tool_get_secure_score(sp: Dict[str, str]) -> Dict[str, Any]:
    from azure.mgmt.security import SecurityCenter
    cred = _sp_cred(sp)
    sc = SecurityCenter(cred, sp["subscription_id"], asc_location="centralus")
    for s in sc.secure_scores.list():
        pct = getattr(s.score, "percentage", None) if getattr(s, "score", None) else None
        if pct is not None:
            v = int(round(float(pct) * 100)) if pct <= 1 else int(round(float(pct)))
            return {"score": v, "max": 100, "name": s.name}
    return {"score": 0, "max": 100, "name": None}


def _tool_get_advisor_recommendations(sp: Dict[str, str], category: Optional[str] = None) -> Dict[str, Any]:
    from azure.mgmt.advisor import AdvisorManagementClient
    cred = _sp_cred(sp)
    ac = AdvisorManagementClient(cred, sp["subscription_id"])
    items = []
    for r in ac.recommendations.list():
        cat = (r.category or "").lower()
        if category and cat != category.lower():
            continue
        items.append({
            "id": r.id,
            "category": r.category,
            "impact": r.impact,
            "problem": (r.short_description.problem if r.short_description else None),
            "solution": (r.short_description.solution if r.short_description else None),
            "resource_id": r.resource_metadata.resource_id if r.resource_metadata else None,
        })
        if len(items) >= 50:
            break
    return {"count": len(items), "recommendations": items}


def _tool_list_alerts(sp: Dict[str, str], top: int = 20) -> Dict[str, Any]:
    from azure.mgmt.monitor import MonitorManagementClient
    cred = _sp_cred(sp)
    mm = MonitorManagementClient(cred, sp["subscription_id"])
    items = []
    for rule in mm.metric_alerts.list_by_subscription():
        items.append({
            "name": rule.name, "enabled": rule.enabled, "severity": rule.severity,
            "description": rule.description, "id": rule.id,
        })
        if len(items) >= top:
            break
    return {"count": len(items), "alerts": items}


def _tool_list_policy_assignments(sp: Dict[str, str], top: int = 50) -> Dict[str, Any]:
    from azure.mgmt.resource.policy import PolicyClient
    cred = _sp_cred(sp)
    pc = PolicyClient(cred, sp["subscription_id"])
    items = []
    for a in pc.policy_assignments.list():
        items.append({
            "name": a.name, "display_name": a.display_name, "scope": a.scope,
            "policy_definition_id": a.policy_definition_id, "id": a.id,
        })
        if len(items) >= top:
            break
    return {"count": len(items), "assignments": items}


def _tool_get_compliance_scores(sp: Dict[str, str]) -> Dict[str, Any]:
    """Return per-framework compliance scores (GDPR, HIPAA, ISO 27001, SOC 2, PCI DSS)."""
    from azure.mgmt.policyinsights import PolicyInsightsClient
    cred = _sp_cred(sp)
    pi = PolicyInsightsClient(cred, sp["subscription_id"])
    total = 0; compliant = 0
    framework_map = {"gdpr": 0, "hipaa": 0, "iso": 0, "soc2": 0, "pci": 0}
    try:
        results = pi.policy_states.list_query_results_for_subscription(
            policy_states_resource="latest", subscription_id=sp["subscription_id"]
        )
        for s in results:
            total += 1
            if (getattr(s, "compliance_state", None) or "").lower() == "compliant":
                compliant += 1
            defn = (getattr(s, "policy_set_definition_name", "") or "").lower()
            for fw in framework_map:
                if fw in defn: framework_map[fw] += 1
    except Exception as e:
        return {"error": str(e), "overall_score": 0, "frameworks": []}
    overall = int(round((compliant / total) * 100)) if total else 0
    return {
        "overall_score": overall, "total_states": total, "compliant_states": compliant,
        "frameworks": [
            {"name": "GDPR", "matches": framework_map["gdpr"], "score": min(100, framework_map["gdpr"] * 10)},
            {"name": "HIPAA", "matches": framework_map["hipaa"], "score": min(100, framework_map["hipaa"] * 10)},
            {"name": "ISO 27001", "matches": framework_map["iso"], "score": min(100, framework_map["iso"] * 10)},
            {"name": "SOC 2", "matches": framework_map["soc2"], "score": min(100, framework_map["soc2"] * 10)},
            {"name": "PCI DSS", "matches": framework_map["pci"], "score": min(100, framework_map["pci"] * 10)},
        ],
    }


def _tool_restart_vm(sp: Dict[str, str], resource_group: str, vm_name: str) -> Dict[str, Any]:
    """Action tool for troubleshoot agent — restart a VM."""
    from azure.mgmt.compute import ComputeManagementClient
    cc = ComputeManagementClient(_sp_cred(sp), sp["subscription_id"])
    poller = cc.virtual_machines.begin_restart(resource_group_name=resource_group, vm_name=vm_name)
    poller.result(timeout=120)
    return {"action": "restart", "vm": vm_name, "resource_group": resource_group, "status": "success"}


def _tool_stop_vm(sp: Dict[str, str], resource_group: str, vm_name: str, deallocate: bool = True) -> Dict[str, Any]:
    from azure.mgmt.compute import ComputeManagementClient
    cc = ComputeManagementClient(_sp_cred(sp), sp["subscription_id"])
    if deallocate:
        poller = cc.virtual_machines.begin_deallocate(resource_group_name=resource_group, vm_name=vm_name)
    else:
        poller = cc.virtual_machines.begin_power_off(resource_group_name=resource_group, vm_name=vm_name)
    poller.result(timeout=180)
    return {"action": "deallocate" if deallocate else "poweroff", "vm": vm_name, "status": "success"}


TOOL_HANDLERS = {
    "list_resource_groups": _tool_list_resource_groups,
    "list_resources": _tool_list_resources,
    "list_vms": _tool_list_vms,
    "get_costs": _tool_get_costs,
    "get_secure_score": _tool_get_secure_score,
    "get_advisor_recommendations": _tool_get_advisor_recommendations,
    "list_alerts": _tool_list_alerts,
    "list_policy_assignments": _tool_list_policy_assignments,
    "get_compliance_scores": _tool_get_compliance_scores,
    "restart_vm": _tool_restart_vm,
    "stop_vm": _tool_stop_vm,
}


TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "list_resource_groups",
        "description": "List all Azure resource groups in the user's subscription.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "list_resources",
        "description": "List Azure resources; optionally filter by resource_group or resource_type (e.g. 'Microsoft.Compute/virtualMachines').",
        "parameters": {"type": "object", "properties": {
            "resource_group": {"type": "string", "description": "Optional RG name filter"},
            "resource_type": {"type": "string", "description": "Optional ARM type filter"},
            "top": {"type": "integer", "description": "Max items (default 200)"},
        }},
    }},
    {"type": "function", "function": {
        "name": "list_vms",
        "description": "List all virtual machines in the subscription with name, location, size, os.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_costs",
        "description": "Get month-to-date cost. If top_n_by_resource>0, returns top N most expensive resources.",
        "parameters": {"type": "object", "properties": {
            "top_n_by_resource": {"type": "integer", "description": "Return top-N resources by cost (e.g. 10)"},
        }},
    }},
    {"type": "function", "function": {
        "name": "get_secure_score",
        "description": "Return Microsoft Defender for Cloud secure score for the subscription.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_advisor_recommendations",
        "description": "Get Azure Advisor recommendations. Optional category: Cost, Security, Performance, HighAvailability, OperationalExcellence.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "list_alerts",
        "description": "List active Azure Monitor metric alert rules configured in the subscription.",
        "parameters": {"type": "object", "properties": {"top": {"type": "integer"}}},
    }},
    {"type": "function", "function": {
        "name": "list_policy_assignments",
        "description": "List Azure Policy assignments at subscription scope.",
        "parameters": {"type": "object", "properties": {"top": {"type": "integer"}}},
    }},
    {"type": "function", "function": {
        "name": "get_compliance_scores",
        "description": "Return per-framework compliance scores (GDPR, HIPAA, ISO 27001, SOC 2, PCI DSS) with overall score derived from Azure Policy compliance states.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "restart_vm",
        "description": "ACTION: Restart an Azure VM. Requires user's explicit request and must confirm resource_group + vm_name.",
        "parameters": {"type": "object", "properties": {
            "resource_group": {"type": "string"}, "vm_name": {"type": "string"},
        }, "required": ["resource_group", "vm_name"]},
    }},
    {"type": "function", "function": {
        "name": "stop_vm",
        "description": "ACTION: Stop (deallocate) an Azure VM. Requires explicit user request.",
        "parameters": {"type": "object", "properties": {
            "resource_group": {"type": "string"}, "vm_name": {"type": "string"},
            "deallocate": {"type": "boolean", "description": "true to deallocate (stop billing), false to just power off"},
        }, "required": ["resource_group", "vm_name"]},
    }},
]


# ---------- OpenAI client factory ----------

async def _openai_client(db, user: dict):
    cfg = await load_user_config(db, user) or {}
    api_key = cfg.get("api_key")
    endpoint = cfg.get("endpoint") or cfg.get("project_endpoint")
    deployment = cfg.get("deployment") or cfg.get("model_name") or "gpt-4o"
    if endpoint and api_key:
        # Azure OpenAI: use base URL as-is (strip trailing slash). SDK will append /chat/completions.
        return AsyncOpenAI(api_key=api_key, base_url=endpoint.rstrip("/")), deployment, "azure_openai"
    # Fallback: Emergent LLM key (dev only — budget-limited)
    import os
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if emergent_key:
        return AsyncOpenAI(api_key=emergent_key, base_url="https://integrations.emergentagent.com/llm/openai/v1"), "gpt-4o", "openai_fallback"
    raise RuntimeError("No AI provider configured. Set Azure OpenAI in Settings.")


async def _load_sp(db, user: dict) -> Optional[Dict[str, str]]:
    tenant = user.get("azure_tenant") or {}
    if not tenant.get("tenant_id"):
        return None
    sec = await db.secrets.find_one({"user_id": user["id"]}) or {}
    secret = sec.get("azure_client_secret")
    if not secret:
        return None
    return {
        "tenant_id": tenant["tenant_id"],
        "subscription_id": tenant["subscription_id"],
        "client_id": tenant["client_id"],
        "client_secret": secret,
    }


# ---------- Main entry ----------

SYSTEM_PROMPT_DEFAULT = """You are InfraGenie, an expert Azure cloud operations copilot for the user's tenant. \
When the user asks about their tenant (resources, costs, VMs, security, policies, alerts, recommendations) you MUST call the appropriate tools; NEVER guess. \
Always answer with concrete numbers pulled from tools. Format money to 2 decimal places with currency. Be concise, action-oriented, and cite the resource IDs when relevant. \
When the user asks for suggestions (cost saving, security fixes, troubleshooting), first pull real tenant data via tools, then reason over it."""


async def tenant_chat(
    db,
    user: dict,
    messages: List[Dict[str, str]],
    hint: Optional[str] = None,
    system_prompt: Optional[str] = None,
    max_tool_iterations: int = 4,
) -> Dict[str, Any]:
    """Run a chat turn with function-calling against the user's tenant.

    messages: list of {"role": "user"|"assistant", "content": "..."}
    Returns: {"reply": str, "tool_traces": [{"tool":..., "args":..., "result_summary":...}], "provider": ...}
    """
    client, deployment, provider = await _openai_client(db, user)
    sp = await _load_sp(db, user)

    sys_prompt = system_prompt or SYSTEM_PROMPT_DEFAULT
    if hint:
        sys_prompt += f"\n\nContext hint from portal: {hint}"
    if not sp:
        sys_prompt += "\n\nWARNING: no Azure Service Principal configured — you cannot query the tenant. Tell the user to configure it in Settings."

    convo = [{"role": "system", "content": sys_prompt}] + messages

    tool_traces: List[Dict[str, Any]] = []

    for _ in range(max_tool_iterations):
        try:
            completion = await client.chat.completions.create(
                model=deployment,
                messages=convo,
                tools=TOOLS_SCHEMA if sp else None,
                tool_choice="auto" if sp else "none",
                temperature=0.2,
            )
        except Exception:
            completion = await client.chat.completions.create(
                model=deployment,
                messages=convo,
                tools=TOOLS_SCHEMA if sp else None,
                tool_choice="auto" if sp else "none",
            )
        msg = completion.choices[0].message
        if not msg.tool_calls:
            return {"reply": (msg.content or "").strip(), "tool_traces": tool_traces, "provider": provider}

        # Append assistant tool-call message
        convo.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls],
        })

        # Execute each tool
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            handler = TOOL_HANDLERS.get(fn_name)
            if not handler or not sp:
                result = {"error": f"tool {fn_name} not available"}
            else:
                try:
                    result = await _run_blocking(handler, sp, **args)
                except Exception as e:  # noqa: BLE001
                    logger.exception("tool %s failed", fn_name)
                    result = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
            tool_traces.append({"tool": fn_name, "args": args, "result_size": len(json.dumps(result))})
            convo.append({
                "role": "tool", "tool_call_id": tc.id, "name": fn_name,
                "content": json.dumps(result)[:12000],  # cap to avoid runaway context
            })

    # Ran out of iterations — force final answer without tools
    try:
        final = await client.chat.completions.create(model=deployment, messages=convo, temperature=0.2)
    except Exception:
        final = await client.chat.completions.create(model=deployment, messages=convo)
    return {"reply": (final.choices[0].message.content or "").strip(), "tool_traces": tool_traces, "provider": provider}
