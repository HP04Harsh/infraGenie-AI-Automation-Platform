"""Test cost estimation for linux-vm-nginx module."""
import asyncio
from pricing_service import estimate_cost

async def main():
    tfvars = {
        "name": "Server1",
        "location": "centralindia",
        "vm_size": "Standard_D2s_v3",
    }
    result = await estimate_cost("linux-vm-nginx", tfvars)
    print(f"Total: {result['monthly_total']} {result['currency']}/mo")
    for b in result["breakdown"]:
        print(f"  {b['label']}: {b['monthly']} {result['currency']}/mo")
    print(f"Suggestions: {result['optimization_suggestions']}")

asyncio.run(main())
