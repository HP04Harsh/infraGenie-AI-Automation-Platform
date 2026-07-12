"""Infracost CLI wrapper for enriched Terraform cost breakdowns.
    
Runs `infracost breakdown` against staged Terraform directories or plan JSON files.
Falls back gracefully if Infracost is unavailable or unconfigured.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("infracost")

INFRACOST_BIN = shutil.which("infracost") or "/usr/local/bin/infracost"
INFRACOST_API_KEY = os.environ.get("INFRACOST_API_KEY", "")
INFRACOST_PRICING_API_ENDPOINT = os.environ.get("INFRACOST_PRICING_API_ENDPOINT", "")
INFRACOST_CLI_AUTH_TOKEN = os.environ.get("INFRACOST_CLI_AUTH_TOKEN", "")


async def _run_infracost(args: list[str], cwd: Path, timeout: int = 60) -> Optional[Dict[str, Any]]:
    if not INFRACOST_API_KEY and not INFRACOST_CLI_AUTH_TOKEN:
        logger.debug("Infracost not configured, skipping")
        return None
    env = os.environ.copy()
    env["INFRACOST_API_KEY"] = INFRACOST_API_KEY
    if INFRACOST_PRICING_API_ENDPOINT:
        env["INFRACOST_PRICING_API_ENDPOINT"] = INFRACOST_PRICING_API_ENDPOINT
    if INFRACOST_CLI_AUTH_TOKEN:
        env["INFRACOST_CLI_AUTH_TOKEN"] = INFRACOST_CLI_AUTH_TOKEN
    full_args = [INFRACOST_BIN] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *full_args, cwd=str(cwd), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = (stdout or b"").decode("utf-8", "replace")
        err = (stderr or b"").decode("utf-8", "replace")
        if proc.returncode != 0:
            logger.warning("Infracost exited %d: %s", proc.returncode, err[:200])
            return None
        if not out.strip():
            return None
        # Parse JSON from stdout — find first '{' and parse everything from there
        idx = out.find("{")
        if idx < 0:
            return None
        return json.loads(out[idx:])
    except asyncio.TimeoutError:
        logger.warning("Infracost timed out after %ds", timeout)
    except Exception as e:
        logger.debug("Infracost error: %s", e)
    return None


async def estimate_with_infracost(
    tf_dir: Path,
    module_key: str,
    tfvars: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run `infracost scan` on a Terraform directory and return cost data.
    
    Returns None if Infracost is unavailable or the run fails.
    """
    if not tf_dir or not tf_dir.exists():
        return None

    result = await _run_infracost(
        ["scan", "--json", str(tf_dir)],
        cwd=tf_dir,
        timeout=180,
    )
    if not result:
        return None

    return _parse_infracost_output(result, module_key)


def _extract_cost_components(item: Dict[str, Any], currency: str) -> list[Dict[str, Any]]:
    """Extract cost items from a resource or its subresources."""
    items: list[Dict[str, Any]] = []
    for comp in item.get("cost_components") or []:
        monthly = float(comp.get("total_monthly_cost") or 0)
        if monthly > 0:
            items.append({
                "name": comp.get("name", ""),
                "monthly": monthly,
            })
    for sub in item.get("subresources") or []:
        items.extend(_extract_cost_components(sub, currency))
    return items


def _parse_infracost_output(data: Dict[str, Any], module_key: str) -> Dict[str, Any]:
    """Convert Infracost v2 scan JSON output to the app's cost breakdown shape."""
    summary = data.get("summary") or {}
    total_monthly = float(summary.get("total_monthly_cost") or 0)
    currency = data.get("currency", "USD")
    projects = data.get("projects") or []
    breakdown: list[Dict[str, Any]] = []

    for proj in projects:
        for r in proj.get("resources") or []:
            name = r.get("name", "unknown")
            resource_type = r.get("type", "")
            is_free = r.get("is_free", False)
            components = _extract_cost_components(r, currency)
            monthly = sum(c["monthly"] for c in components)

            if monthly == 0 and is_free:
                continue

            note = "; ".join(
                f"{c['name']} = {c['monthly']:.2f} {currency}/mo"
                for c in components
            ) if components else ("free" if is_free else "unknown")

            breakdown.append({
                "label": f"{resource_type} — {name}",
                "monthly": round(monthly, 2),
                "note": note,
            })

    if not breakdown:
        return None

    suggestions = ["Cost data sourced from Infracost CLI"]
    if total_monthly > 0:
        suggestions.append("Enable Azure Cost Alerts on this resource group to catch anomalies.")

    return {
        "monthly_total": round(total_monthly, 2),
        "currency": currency,
        "breakdown": breakdown,
        "one_time": 0.0,
        "optimization_suggestions": suggestions,
        "source": "infracost",
    }
