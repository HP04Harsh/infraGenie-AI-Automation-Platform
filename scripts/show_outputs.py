"""Show deployment outputs."""
import asyncio, httpx, json

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    r = httpx.get('http://localhost:8000/api/provisioning/sessions/749ba891-6060-477d-b9a4-4e5d97da2c5a', headers=headers, timeout=10)
    s = r.json()
    print('Status:', s['status'])
    print('Module:', s['module_key'])
    print('\nCollected vars:')
    for k, v in s.get('collected_vars', {}).items():
        if k != 'admin_password':
            print(f'  {k}: {v}')
    
    plan = s.get('plan', {})
    outputs = plan.get('outputs', [])
    print('\nOutputs:')
    for o in outputs:
        print(f'  {o["name"]}: {o.get("value_preview", "")}')
    
    cost = plan.get('cost', {})
    print(f'\nCost: ${cost.get("monthly_total", "?")}/mo ({cost.get("source", "?")})')
    
    if outputs:
        public_ip = next((o.get('value_preview', '') for o in outputs if o['name'] == 'public_ip'), '')
        http_url = next((o.get('value_preview', '') for o in outputs if o['name'] == 'http_url'), '')
        ssh_cmd = next((o.get('value_preview', '') for o in outputs if o['name'] == 'ssh_command'), '')
        print(f'\nPublic IP: {public_ip}')
        print(f'HTTP URL: {http_url}')
        print(f'SSH: {ssh_cmd}')

asyncio.run(main())
