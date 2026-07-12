"""ServiceNow integration: create/update incidents via REST API."""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

SYS_USER_SYS_ID_CACHE: Dict[str, str] = {}


async def _get_sn_creds(db, user_id: str) -> Optional[Dict[str, str]]:
    conn = await db.integrations.find_one({"user_id": user_id, "key": "servicenow"})
    secret = await db.integration_secrets.find_one({"user_id": user_id, "key": "servicenow"})
    if not (conn and conn.get("connected") and secret):
        return None
    return {
        "instance_url": (conn.get("fields") or {}).get("instance_url", "").rstrip("/"),
        "username": (conn.get("fields") or {}).get("username", ""),
        "password": secret.get("password", ""),
    }


async def _resolve_user_sys_id(sn: Dict[str, str], email: str) -> Optional[str]:
    """Resolve a user email to a ServiceNow sys_user sys_id."""
    if not email or not sn:
        return None
    cached = SYS_USER_SYS_ID_CACHE.get(email)
    if cached:
        return cached
    url = f"{sn['instance_url']}/api/now/table/sys_user"
    params = {"sysparm_query": f"email={email}", "sysparm_fields": "sys_id", "sysparm_limit": "1"}
    async with httpx.AsyncClient(auth=(sn["username"], sn["password"]), timeout=10.0) as c:
        r = await c.get(url, params=params)
        if r.status_code == 200:
            results = r.json().get("result", [])
            if results:
                sys_id = results[0]["sys_id"]
                SYS_USER_SYS_ID_CACHE[email] = sys_id
                return sys_id
    return None


async def health_check(db, user_id: str) -> Dict[str, Any]:
    sn = await _get_sn_creds(db, user_id)
    if not sn:
        return {"connected": False}
    url = f"{sn['instance_url']}/api/now/table/incident?sysparm_limit=1"
    async with httpx.AsyncClient(auth=(sn["username"], sn["password"]), timeout=10.0) as c:
        r = await c.get(url)
        return {"connected": r.status_code == 200, "status_code": r.status_code}


async def create_incident(
    db, user_id: str,
    short_description: str,
    description: str = "",
    caller_email: str = "",
    watch_list: str = "",
    severity: int = 3,
    assignment_group: str = "",
) -> Optional[Dict[str, Any]]:
    sn = await _get_sn_creds(db, user_id)
    if not sn:
        logger.warning("ServiceNow not configured, skipping incident creation")
        return None

    body: Dict[str, Any] = {
        "short_description": short_description[:160],
        "description": description,
        "impact": str(severity),
        "urgency": str(severity),
        "contact_type": "email",
    }
    # Resolve caller_email to a valid sys_user sys_id (caller_id is a reference field)
    if caller_email:
        caller_sys_id = await _resolve_user_sys_id(sn, caller_email)
        if caller_sys_id:
            body["caller_id"] = caller_sys_id
    # watch_list accepts comma-separated email addresses natively
    if watch_list:
        body["watch_list"] = watch_list
    elif caller_email:
        body["watch_list"] = caller_email
    if assignment_group:
        body["assignment_group"] = assignment_group
    # Assign to the integration user so incidents appear in their task list
    if sn.get("username"):
        assign_url = f"{sn['instance_url']}/api/now/table/sys_user?sysparm_query=user_name={sn['username']}&sysparm_fields=sys_id"
        async with httpx.AsyncClient(auth=(sn["username"], sn["password"]), timeout=10.0) as c:
            ar = await c.get(assign_url)
            if ar.status_code == 200:
                assign_results = ar.json().get("result", [])
                if assign_results:
                    body["assigned_to"] = assign_results[0]["sys_id"]

    url = f"{sn['instance_url']}/api/now/table/incident"
    async with httpx.AsyncClient(auth=(sn["username"], sn["password"]), timeout=15.0) as c:
        r = await c.post(url, json=body)
        if r.status_code == 201:
            result = r.json().get("result", {})
            logger.info("ServiceNow incident %s created (caller=%s)", result.get("number"), body.get("caller_id", "none"))
            return result
        logger.error("ServiceNow incident creation failed: %d %s", r.status_code, r.text[:300])
        return None


async def update_incident(db, user_id: str, sys_id: str, fields: Dict[str, Any]) -> bool:
    sn = await _get_sn_creds(db, user_id)
    if not sn:
        return False
    url = f"{sn['instance_url']}/api/now/table/incident/{sys_id}"
    async with httpx.AsyncClient(auth=(sn["username"], sn["password"]), timeout=15.0) as c:
        r = await c.patch(url, json=fields)
        return r.status_code == 200
