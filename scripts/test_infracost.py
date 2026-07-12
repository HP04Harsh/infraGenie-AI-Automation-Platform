import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
s = d["summary"]
print(f"Total: ${s['total_monthly_cost']}/mo ({s['costed_resources']} costed + {s['free_resources']} free = {s['resources']} resources)")
for p in d["projects"]:
    for r in p["resources"]:
        if not r.get("is_free", True):
            total = 0
            for c in r.get("cost_components", []):
                total += float(c.get("total_monthly_cost", 0))
            for sr in r.get("subresources", []):
                for c in sr.get("cost_components", []):
                    total += float(c.get("total_monthly_cost", 0))
            print(f"  {r['type']} - {r['name']}: ${total:.2f}/mo")
