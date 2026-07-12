"""Verify fixes: session outputs, ticket names, itsm chat."""
import asyncio, httpx, json

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    # 1. Check session outputs
    print("=== SESSION OUTPUTS ===")
    r = httpx.get('http://localhost:8000/api/provisioning/sessions/749ba891-6060-477d-b9a4-4e5d97da2c5a', headers=headers, timeout=10)
    s = r.json()
    plan = s.get('plan', {})
    for o in plan.get('outputs', []):
        print(f"  {o['name']}: {o.get('value_preview', '')}")
    
    # 2. Check ticket deployment_name
    print("\n=== TICKET NAMES ===")
    r = httpx.get('http://localhost:8000/api/tickets', headers=headers, timeout=10)
    for t in r.json().get('items', []):
        print(f"  {t['ticket_number']}: deployment_name={t.get('deployment_name','?')}")
    
    # 3. Test ITSM chat
    print("\n=== ITSM CHAT ===")
    r = httpx.post('http://localhost:8000/api/itsm/chat', headers=headers, json={"message": "list my tickets"}, timeout=60)
    print(f"Chat list: {r.status_code}")
    print(r.json().get('reply', '')[:500])

    r = httpx.post('http://localhost:8000/api/itsm/chat', headers=headers, json={"message": "create a ticket for storage account backup failure"}, timeout=120)
    print(f"\nChat create: {r.status_code}")
    print(r.json().get('reply', '')[:500])
    ticket = r.json().get('ticket')
    if ticket:
        print(f"Ticket created: {ticket.get('ticket_number')} synced={ticket.get('servicenow_synced')}")

asyncio.run(main())
