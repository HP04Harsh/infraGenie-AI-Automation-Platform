"""Check deployment status and wait for completion."""
import httpx, time

BASE = "http://localhost:8000/api"
login = httpx.post(f"{BASE}/auth/login", json={
    "email": "guest@infragenie.io", "password": "Guest@321"
}, timeout=10)
token = login.cookies.get("ig_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

r = httpx.get(f"{BASE}/provisioning/sessions", headers=headers, timeout=10)
sessions = r.json().get("sessions", [])

# Find the last session in non-collecting status
for s in reversed(sessions):
    if s.get("status") not in ("collecting", "ready"):
        sid = s["id"]
        status = s.get("status")
        print(f"Session: {sid[:12]}... status={status}")
        
        # Wait for completion
        for attempt in range(60):
            r2 = httpx.get(f"{BASE}/provisioning/sessions/{sid}", headers=headers, timeout=10)
            if r2.status_code != 200:
                print(f"  Error fetching: {r2.status_code}")
                break
            s2 = r2.json()
            st = s2.get("status")
            deploy = s2.get("deployment", {})
            ticket_num = s2.get("ticket_number")
            sn_num = deploy.get("servicenow_number") if deploy else s2.get("servicenow_number")
            
            if st in ("completed", "failed"):
                print(f"  Final status: {st} (after {attempt*10}s)")
                if sn_num:
                    print(f"  ServiceNow: {sn_num}")
                if st == "failed":
                    print(f"  Error: {deploy.get('error','')[:500] if deploy else 'unknown'}")
                break
            
            if attempt % 3 == 0:
                print(f"  Status={st}, SN={sn_num}, elapsed={attempt*10}s")
            time.sleep(10)
        break
