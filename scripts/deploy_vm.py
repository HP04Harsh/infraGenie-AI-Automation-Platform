"""Deploy Standard_D2s_v3 in westus2."""
import httpx, json, sys, time

BASE = "http://localhost:8000/api"

# Login
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK, user:", login.json().get("user", {}).get("id"))

# Create provisioning session
r = httpx.post(f"{BASE}/provisioning/sessions", json={"module_key": "linux-vm-nginx"}, headers=headers, timeout=10)
sid = r.json().get("id")
if not sid:
    print("Failed to create session:", r.text)
    sys.exit(1)
print(f"Session: {sid}")

# Chat to auto-fill all vars with desired values
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json={
    "message": "server01 for nginx hosting"
}, timeout=15)
print("Chat 1:", r.status_code)

r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json={
    "message": "use default everything. azure region is westus2. vm size is Standard_D2s_v3. admin username is Harsh. auth mode is password and password is Harsh@321456"
}, timeout=15)
print("Chat 2:", r.status_code)

r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/chat", headers=headers, json={
    "message": "generate plan"
}, timeout=15)
print("Chat 3:", r.status_code)

# Generate plan
print("Generating plan...")
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/plan", headers=headers, timeout=120)
print(f"Plan: {r.status_code}")
plan = r.json()
summary = plan.get("summary", "no summary")
cost = plan.get("cost", {})
print(f"Summary: {summary}")
print(f"Cost: ${cost.get('monthly_total', '?')}/mo")

if cost.get("source") == "infracost":
    for item in cost.get("breakdown", []):
        print(f"  {item['label']}: ${item['monthly']}/mo")

# Approve
print("Approving deployment...")
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"approved": True}, timeout=600)
print(f"Approve: {r.status_code}")
result = r.json()
print(f"Status: {result.get('status')}")
logs = result.get("logs", [])
if logs:
    for line in logs[-5:]:
        print(f"  {line}")
outputs = result.get("outputs", {})
if outputs:
    print(f"Outputs: {json.dumps(outputs, indent=2)}")
