"""Find awaiting_approval session and approve it."""
import httpx

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

r = httpx.get(f"{BASE}/provisioning/sessions", headers=headers, timeout=10)
sessions = r.json().get("sessions", [])

# Find awaiting_approval session
target = None
for s in sessions:
    print(f"  {s['id'][:12]}... status={s.get('status')}")
    if s.get("status") == "awaiting_approval":
        target = s
        break

if not target:
    print("No awaiting_approval session found")
    exit()

sid = target["id"]
print(f"\nApproving session {sid}")
r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"decision": "approved"}, timeout=600)
print(f"Approve: {r.status_code}")
print(f"Body: {r.text[:1500]}")
