"""Check all sessions to find the one we approved."""
import httpx

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

r = httpx.get(f"{BASE}/provisioning/sessions", headers=headers, timeout=10)
sessions = r.json().get("sessions", [])

# Check the approved session
for s in reversed(sessions):
    sid = s["id"]
    r2 = httpx.get(f"{BASE}/provisioning/sessions/{sid}", headers=headers, timeout=10)
    if r2.status_code != 200:
        continue
    s2 = r2.json()
    print(f"  {sid[:12]}... status={s2.get('status')} ticket_number={s2.get('ticket_number')} module={s2.get('module_key')}")
