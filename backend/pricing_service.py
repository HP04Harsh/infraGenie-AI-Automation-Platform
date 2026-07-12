"""Azure Retail Pricing service.

Queries https://prices.azure.com/api/retail/prices (no auth required) to compute
real monthly cost estimates for deployed resources.

Docs: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("pricing")

RETAIL_URL = "https://prices.azure.com/api/retail/prices"

try:
    from redis_cache import cache_get, cache_set
except ImportError:
    async def cache_get(key): return None
    async def cache_set(key, value, ttl=300): return False

# Currency depends on Azure billing region. India / centralindia is INR-billed.
REGION_CURRENCY = {
    "centralindia": "INR", "southindia": "INR", "westindia": "INR",
    "eastus": "USD", "eastus2": "USD", "westus": "USD", "westus2": "USD", "westus3": "USD",
    "centralus": "USD", "northeurope": "EUR", "westeurope": "EUR",
    "uksouth": "GBP", "ukwest": "GBP",
    "japaneast": "JPY", "japanwest": "JPY",
    "australiaeast": "AUD",
    "canadacentral": "CAD",
    "brazilsouth": "BRL",
}

USD_TO_INR = 83.0  # rough fallback if we can't get INR quoted directly


def _hours_per_month() -> float:
    return 730.0  # Azure standard


async def _query(filter_expr: str, currency: str = "INR", limit: int = 20) -> List[Dict[str, Any]]:
    cache_key = f"pricing:q:{hashlib.sha256(filter_expr.encode()).hexdigest()[:16]}:{currency}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    params = {"$filter": filter_expr, "currencyCode": currency, "$top": str(limit)}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(RETAIL_URL, params=params)
            if r.status_code == 200:
                items = (r.json() or {}).get("Items", [])
                await cache_set(cache_key, items, ttl=3600)
                return items
    except Exception as e:
        logger.warning("Retail pricing query failed: %s", e)
    return []


def _pick_cheapest_hourly(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the cheapest 1-hour meter (skip reserved/spot for baseline)."""
    consumption = [
        i for i in items
        if (i.get("type") == "Consumption")
        and (i.get("unitOfMeasure") in ("1 Hour", "1 Hours"))
        and (i.get("reservationTerm") in (None, "", "0"))
    ]
    if not consumption:
        return items[0] if items else None
    return min(consumption, key=lambda x: float(x.get("retailPrice") or 0.0))


# ---------- Module-specific cost functions ----------
async def cost_virtual_machine(size: str, region: str, currency: str) -> Dict[str, Any]:
    filt = (
        f"serviceName eq 'Virtual Machines' and armSkuName eq '{size}' "
        f"and armRegionName eq '{region}' and priceType eq 'Consumption'"
    )
    items = await _query(filt, currency=currency)
    m = _pick_cheapest_hourly(items)
    if not m:
        return {"label": "Compute", "monthly": 0.0, "note": "SKU not found in retail pricing"}
    hourly = float(m.get("retailPrice") or 0)
    monthly = hourly * _hours_per_month()
    return {"label": f"{size} VM (compute)", "monthly": round(monthly, 2),
            "note": f"{hourly:.4f} {currency}/hr × 730h/mo"}


async def cost_storage_account(tier: str, replication: str, region: str, currency: str) -> Dict[str, Any]:
    filt = (
        f"serviceName eq 'Storage' and armRegionName eq '{region}' "
        f"and contains(productName,'General Block Blob')"
    )
    items = await _query(filt, currency=currency)
    # Rough baseline — assume 100 GB stored @ hot tier
    m = _pick_cheapest_hourly(items) or (items[0] if items else None)
    if not m:
        return {"label": "Storage (100 GB baseline)", "monthly": 0.0}
    per_gb = float(m.get("retailPrice") or 0)
    monthly = per_gb * 100.0
    return {"label": f"{tier} {replication} (100 GB baseline)", "monthly": round(monthly, 2),
            "note": f"{per_gb:.4f} {currency}/GB-mo"}


async def cost_sql_database(sku: str, region: str, currency: str) -> Dict[str, Any]:
    filt = (
        f"serviceName eq 'SQL Database' and armRegionName eq '{region}' "
        f"and contains(skuName,'{sku}')"
    )
    items = await _query(filt, currency=currency)
    m = _pick_cheapest_hourly(items)
    if not m:
        return {"label": f"SQL Database ({sku})", "monthly": 0.0}
    hourly = float(m.get("retailPrice") or 0)
    monthly = hourly * _hours_per_month()
    return {"label": f"SQL Database ({sku})", "monthly": round(monthly, 2),
            "note": f"{hourly:.4f} {currency}/hr × 730h/mo"}


async def cost_app_service(sku: str, region: str, currency: str) -> Dict[str, Any]:
    filt = (
        f"serviceName eq 'Azure App Service' and armRegionName eq '{region}' "
        f"and contains(skuName,'{sku}')"
    )
    items = await _query(filt, currency=currency)
    m = _pick_cheapest_hourly(items)
    if not m:
        return {"label": f"App Service ({sku})", "monthly": 0.0}
    hourly = float(m.get("retailPrice") or 0)
    monthly = hourly * _hours_per_month()
    return {"label": f"App Service Plan ({sku})", "monthly": round(monthly, 2),
            "note": f"{hourly:.4f} {currency}/hr × 730h/mo"}


# ---------- Public entry point ----------
def _cost_cache_key(module_key: str, tfvars: Dict[str, Any], action: str) -> str:
    raw = json.dumps({"m": module_key, "v": tfvars, "a": action}, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"cost:{module_key}:{h}"


async def estimate_cost(module_key: str, tfvars: Dict[str, Any], action: str = "create") -> Dict[str, Any]:
    """Return {monthly_total, currency, breakdown[], one_time, optimization_suggestions[]}.

    On destroy, returns zero cost + savings note. On modify, treats as create (best-effort).
    Results are cached in Redis for 1 hour.
    """
    ck = _cost_cache_key(module_key, tfvars, action)
    cached = await cache_get(ck)
    if cached is not None:
        logger.debug("Cost cache HIT for %s", ck)
        return cached

    region = str(tfvars.get("location") or "centralindia").lower().replace(" ", "")
    currency = REGION_CURRENCY.get(region, "USD")

    if action == "destroy":
        return {
            "monthly_total": 0.0, "currency": currency,
            "breakdown": [{"label": "Resources removed", "monthly": 0.0}],
            "one_time": 0.0,
            "optimization_suggestions": ["Destroying reclaims all monthly spend for these resources."],
        }

    breakdown: List[Dict[str, Any]] = []

    try:
        if module_key == "virtual-machine-linux" or module_key == "virtual-machine-windows":
            size = tfvars.get("vm_size") or "Standard_B2s"
            breakdown.append(await cost_virtual_machine(size, region, currency))
            breakdown.append({"label": "OS Disk (Standard_LRS 30 GB)", "monthly": 2.3 if currency == "USD" else 190.0})
            breakdown.append({"label": "NIC (free)", "monthly": 0.0})
        elif module_key == "linux-vm-nginx":
            size = tfvars.get("vm_size") or "Standard_B2s"
            breakdown.append(await cost_virtual_machine(size, region, currency))
            breakdown.append({"label": "OS Disk (Standard_LRS 30 GB)", "monthly": 2.3 if currency == "USD" else 190.0})
            breakdown.append({"label": "Public IP (Standard Static)", "monthly": 3.6 if currency == "USD" else 300.0})
            breakdown.append({"label": "NIC (free)", "monthly": 0.0})
            breakdown.append({"label": "VNet / Subnet / NSG (free)", "monthly": 0.0, "note": "No standalone billing meter"})
        elif module_key == "storage-account":
            breakdown.append(await cost_storage_account(
                tfvars.get("account_tier", "Standard"),
                tfvars.get("replication_type", "LRS"),
                region, currency,
            ))
        elif module_key == "sql-database":
            breakdown.append(await cost_sql_database(tfvars.get("sku_name", "S0"), region, currency))
        elif module_key == "app-service":
            breakdown.append(await cost_app_service(tfvars.get("sku_name", "B1"), region, currency))
        elif module_key == "key-vault":
            breakdown.append({"label": f"Key Vault ({tfvars.get('sku_name','standard')})", "monthly": 0.03 * 730 if currency == "USD" else 2.5 * 730})
        elif module_key == "function-app":
            breakdown.append({"label": "Function App (Y1 consumption)", "monthly": 0.0,
                              "note": "Consumption plan — pay per execution"})
        elif module_key == "load-balancer":
            breakdown.append({"label": f"Load Balancer ({tfvars.get('sku','Standard')})", "monthly": 18.5 if currency == "USD" else 1540.0})
        elif module_key == "public-ip":
            breakdown.append({"label": "Public IP (Standard Static)", "monthly": 3.6 if currency == "USD" else 300.0})
        elif module_key in ("virtual-network", "subnet", "network-security-group", "managed-identity", "resource-group"):
            breakdown.append({"label": "Resource is free", "monthly": 0.0,
                              "note": "No standalone billing meter"})
    except Exception as e:
        logger.exception("estimate_cost failed: %s", e)

    total = sum(float(b.get("monthly") or 0) for b in breakdown)

    suggestions: List[str] = []
    if module_key.startswith("virtual-machine") and tfvars.get("vm_size", "").startswith("Standard_D"):
        suggestions.append("Consider Standard_B-series burstable VMs for dev/test workloads to cut compute cost ~40%.")
    if module_key == "storage-account" and tfvars.get("replication_type") == "GRS":
        suggestions.append("If the workload doesn't need geo-redundancy, LRS costs ~50% less.")
    if module_key == "sql-database" and tfvars.get("sku_name") in ("S1", "S2", "S3"):
        suggestions.append("For dev workloads consider Basic tier or serverless General Purpose Gen5.")
    if total > 0:
        suggestions.append("Enable Azure Cost Alerts on this resource group to catch anomalies.")

    result = {
        "monthly_total": round(total, 2),
        "currency": currency,
        "breakdown": breakdown,
        "one_time": 0.0,
        "optimization_suggestions": suggestions,
    }
    await cache_set(ck, result, ttl=3600)
    return result
