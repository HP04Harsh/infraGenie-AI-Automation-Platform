"""Debug the approve flow on last session."""
import httpx

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get sessions
r = httpx.get(f"{BASE}/provisioning/sessions", headers=headers, timeout=10)
sessions = r.json().get("sessions", [])
latest = sessions[-1] if sessions else None
if not latest:
    print("No sessions found")
    exit()

sid = latest["id"]
print(f"Session: {sid}")
print(f"Status: {latest.get('status')}")

if latest.get("status") == "awaiting_approval":
    r = httpx.post(f"{BASE}/provisioning/sessions/{sid}/approve", headers=headers, json={"approved": True}, timeout=600)
    print(f"Approve: {r.status_code}")
    print(f"Response: {r.text[:1000]}")
else:
    print("Not in awaiting_approval")
