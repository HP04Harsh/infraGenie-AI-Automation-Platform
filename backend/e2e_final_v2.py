"""Full E2E: test cost, defaults flow, approve guard, and real deploy."""
import httpx, time, sys, random

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
assert login.status_code == 200, "Login failed"
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK")

# ---- Test 1: Cost estimation ----
r = httpx.get(f"{BASE}/metrics", headers=headers, timeout=15)
print(f"Metrics: {r.status_code}")

# ---- Test 2: Use defaults flow ----
r = httpx.post(f"{BASE}/provisioning/sessions", headers=headers, json={}, timeout=10)
sid = r.json()["id"]
print(f"\nSession (defaults test): {sid}")

suffix = random.randint(1000,9999)
msg = {"message": f"deploy a linux vm with name srv{suffix} and rg rg-e2e-{suffix}"}
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg, timeout=120)
data = r.json()

# Say "use defaults" to fill any remaining vars
if data.get("status") != "ready":
    msg2 = {"message": "use defaults"}
    r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg2, timeout=120)
    data = r.json()
    print(f"  After 'use defaults': {data.get('status')} — module={data.get('module_key')}")
    assert data.get("status") == "ready", f"Still not ready: {data.get('missing_vars')}"

print(f"  Module: {data.get('module_key')}")
print(f"  Vars: {data.get('collected_vars', {})}")

# ---- Test 3: Plan ----
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/plan", headers=headers, json={}, timeout=600)
assert r.status_code == 200, f"Plan failed: {r.status_code}"
plan = r.json().get("plan", {})
print(f"\nPlan: {plan.get('summary')}")
cost = plan.get("cost", {})
print(f"Cost: {cost.get('monthly_total')} {cost.get('currency')}/mo")
assert cost.get("monthly_total", 0) > 0, "Cost should not be 0!"

# ---- Test 4: Approve guard (double-click) ----
r1 = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"decision": "approved"}, timeout=600)
r2 = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"decision": "approved"}, timeout=600)
print(f"\nApprove 1: {r1.status_code}")
print(f"Approve 2 (double-click): {r2.status_code}")
assert r1.status_code == 200
assert r2.status_code == 200

# Wait for completion
for i in range(300):
    r = httpx.get(f"{BASE}/provisioning/sessions/{sid}", headers=headers, timeout=10)
    s = r.json()
    status = s.get("status")
    if status in ("completed", "failed"):
        print(f"\nDeployment: {status} ({i*10}s)")
        if status == "failed":
            ar = s.get("apply_result", {})
            logs = ar.get("logs", [])
            for l in logs[-5:]:
                print(f"  {l[:200]}")
            sys.exit(1)
        break
    if i % 12 == 0:
        print(f"  Status: {status} ({i*10}s)")
    time.sleep(10)
else:
    print("Timeout")
    sys.exit(1)

print("\nALL TESTS PASSED")
