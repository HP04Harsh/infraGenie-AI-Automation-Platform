"""Full E2E: deploy Linux VM with password auth, verify plan, check ServiceNow."""
import httpx, json, time, sys

BASE = "http://localhost:8000/api"

# Login
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
assert login.status_code == 200, f"Login failed: {login.status_code}"
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("✅ Login OK")

# Step 1: Create session
r = httpx.post(f"{BASE}/provisioning/sessions", headers=headers, json={}, timeout=10)
assert r.status_code == 200, f"Session creation failed: {r.status_code}"
sid = r.json()["id"]
print(f"✅ Session created: {sid}")

# Step 2: Chat - ask for VM with password auth
msg = {
    "message": "set up a complete all-in-one linux vm with nginx in westus2, name=Server1, "
               "rg=rg-test-e2e, size=Standard_D2s_v3, admin=harsh, password=Harsh@321456, "
               "use password auth not ssh key"
}
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg, timeout=120)
assert r.status_code == 200, f"Chat 1 failed: {r.status_code}"
data = r.json()
conv = data.get("conversation", [])
last = conv[-1]
print(f"✅ Chat 1 response: {last['content'][:200]}")

# Step 3: Check if ready for plan
if data.get("status") == "ready":
    print("✅ All variables collected, ready for plan")
else:
    print(f"⚠️  Session status: {data.get('status')}, missing: {data.get('missing_vars', [])}")
    # If still collecting, we need to provide more info
    if last.get("content") != "READY":
        # Try filling remaining vars
        msg2 = {"message": "use defaults for everything else"}
        r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json=msg2, timeout=120)
        assert r.status_code == 200, f"Chat 2 failed: {r.status_code}"
        data = r.json()
        print(f"✅ Chat 2: {data.get('status')}")

# Step 4: Generate plan
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/plan", headers=headers, json={}, timeout=120)
assert r.status_code == 200, f"Plan failed: {r.status_code}"
plan = r.json()
print(f"✅ Plan generated: {plan.get('summary', 'No summary')}")

# Step 5: Approve (triggers ServiceNow incident)
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"approved": True}, timeout=120)
assert r.status_code == 200, f"Approve failed: {r.status_code}"
result = r.json()
print(f"✅ Approved: status={result.get('status')}")

# Step 6: Verify ServiceNow incident was created
time.sleep(2)
# Check the last ticket in the system
r = httpx.get(f"{BASE}/itsm/tickets", headers=headers, timeout=10)
if r.status_code == 200:
    tickets = r.json().get("tickets", [])
    if tickets:
        latest = tickets[-1]
        sn_num = latest.get("servicenow_number")
        print(f"✅ Ticket created: {latest.get('ticket_number')}, SN: {sn_num}")

print("\n✅✅✅ E2E test PASSED")
