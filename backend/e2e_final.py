"""Final E2E: full Linux VM deploy with password auth, verify apply + ServiceNow."""
import httpx, time, sys

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
assert login.status_code == 200, "Login failed"
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK")

# Create session
r = httpx.post(f"{BASE}/provisioning/sessions", headers=headers, json={}, timeout=10)
sid = r.json()["id"]
print(f"Session: {sid}")

# Send request
msg = {"message": "set up a complete all-in-one linux vm with nginx in westus2, name=Server1, rg=rg-e2e-final, size=Standard_D2s_v3, admin=harsh, password=Harsh@321456, use password auth not ssh key"}
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg, timeout=120)
data = r.json()
assert data.get("status") == "ready", f"Not ready: {data.get('status')}"
print("Chat OK - all vars collected")

# Plan
t0 = time.time()
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/plan", headers=headers, json={}, timeout=600)
plan_data = r.json()
plan = plan_data.get("plan", {})
print(f"Plan ({time.time()-t0:.0f}s): {plan.get('summary')}")
assert "Plan:" in (plan.get("summary") or ""), "Plan failed"

# Approve
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"decision": "approved"}, timeout=600)
assert r.status_code == 200, f"Approve failed: {r.status_code}"
print(f"Approve OK - status={r.json().get('status')}")

# Wait for completion
for i in range(300):
    r = httpx.get(f"{BASE}/provisioning/sessions/{sid}", headers=headers, timeout=10)
    s = r.json()
    status = s.get("status")
    if status in ("completed", "failed"):
        print(f"Status: {status} ({i*10}s)")
        if status == "failed":
            print(f"Error: {s.get('apply_result',{}).get('error','')[:500]}")
            sys.exit(1)
        break
    if i % 6 == 0:
        print(f"Status: {status} ({i*10}s)")
    time.sleep(10)
else:
    print("Timeout waiting for completion")
    sys.exit(1)

# Check ServiceNow
sn = s.get("servicenow_number")
print(f"ServiceNow ticket: {sn}")
print("DONE - VM deployed successfully!")
