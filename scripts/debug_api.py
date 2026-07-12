"""Check session API response vs ticket API for outputs."""
import asyncio, httpx, json

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    sid = '749ba891-6060-477d-b9a4-4e5d97da2c5a'
    
    # Session
    r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
    s = r.json()
    print("=== SESSION ===")
    print("status:", s.get('status'))
    
    plan = s.get('plan', {})
    print("plan.outputs:", [o['name'] for o in plan.get('outputs', [])])
    for o in plan.get('outputs', []):
        print(f"  {o['name']}: {o.get('value_preview', '')}")
    
    ar = s.get('apply_result', {})
    print("\napply_result.outputs:", ar.get('outputs', {}))
    
    # Ticket
    r2 = httpx.get(f'http://localhost:8000/api/tickets?session_id={sid}', headers=headers, timeout=10)
    tickets = r2.json().get('items', [])
    print(f"\n=== TICKETS (session match) ===")
    print(f"Found: {len(tickets)}")
    
    # Try listing all tickets
    r3 = httpx.get(f'http://localhost:8000/api/tickets', headers=headers, timeout=10)
    all_tickets = r3.json().get('items', [])
    print(f"\n=== ALL TICKETS ===")
    print(f"Found: {len(all_tickets)}")
    for t in all_tickets:
        print(f"  {t.get('ticket_number')}: {t.get('deployment_name', '?')} - {t.get('status')}")
        print(f"    resource_name: {t.get('resource_name')}")
        print(f"    outputs: {t.get('outputs', {})}")

asyncio.run(main())
