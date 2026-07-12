"""Approve and deploy."""
import asyncio, httpx

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    sid = '749ba891-6060-477d-b9a4-4e5d97da2c5a'
    
    # Get session to see full plan
    r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
    s = r.json()
    plan = s.get('plan', {})
    print('Summary:', plan.get('summary', ''))
    cost = plan.get('cost', {})
    print('Cost monthly:', cost.get('monthly_total', ''))
    print('Cost source:', cost.get('source', ''))
    print('Actions:', len(plan.get('actions', [])))
    for a in plan.get('actions', []):
        print(f"  {a.get('action')}: {a.get('resource_type')} ({a.get('resource_name')})")
    
    # Approve
    print('\nApproving...')
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/approve', headers=headers, json={'decision': 'approved'}, timeout=600)
    print('Approve status:', r.status_code)
    j = r.json()
    print('Result status:', j.get('status'))
    logs = j.get('logs', [])
    if logs:
        for line in logs[-10:]:
            print(f"  {line}")

asyncio.run(main())
