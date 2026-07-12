"""Test plan generation only with longer timeout."""
import httpx, time

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Create session
r = httpx.post(f"{BASE}/provisioning/sessions", headers=headers, json={}, timeout=10)
sid = r.json()["id"]
print(f"Session: {sid}")

# Send request
msg = {"message": "set up a complete all-in-one linux vm with nginx in westus2, name=Server1, rg=rg-test-e2e, size=Standard_D2s_v3, admin=harsh, password=Harsh@321456, use password auth not ssh key"}
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg, timeout=120)
print(f"Chat: {r.status_code} — {r.json().get('status')} — {r.json().get('conversation',[{}])[-1].get('content','')[:100]}")

# Plan
t0 = time.time()
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/plan", headers=headers, json={}, timeout=300)
elapsed = time.time() - t0
data = r.json()
print(f"Plan ({elapsed:.0f}s): {r.status_code}")
if r.status_code == 200:
    plan = data.get("plan", {})
    print(f"  Summary: {plan.get('summary')}")
    print(f"  Actions: {len(plan.get('actions', []))}")
    print(f"  Cost: ${plan.get('cost',{}).get('monthly_total',0)}/mo")
    
    # Approve
    r2 = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"approved": True}, timeout=600)
    print(f"Approve: {r2.status_code} — {r2.json().get('status')}")
    
    # Check deployment status
    deploy = r2.json().get("deployment", {})
    if deploy:
        print(f"  Deployment ID: {deploy.get('id')}")
        print(f"  Status: {deploy.get('status')}")
        sn = deploy.get("servicenow_number")
        print(f"  ServiceNow: {sn}")
else:
    print(f"  Error: {data.get('error','')[:500]}")
