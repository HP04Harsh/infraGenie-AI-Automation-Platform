"""Set vars in session, call plan, print full response."""
import asyncio, httpx, datetime, json
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    
    sid = '749ba891-6060-477d-b9a4-4e5d97da2c5a'
    vars_map = {
        'name': 'server01',
        'resource_group_name': 'rg-server01',
        'location': 'westus2',
        'vm_size': 'Standard_D2s_v3',
        'admin_username': 'Harsh',
        'admin_password': 'Harsh@321456'
    }
    
    await db.provisioning_sessions.update_one(
        {'id': sid},
        {'$set': {
            'collected_vars': vars_map,
            'missing_vars': [],
            'status': 'ready',
            'updated_at': datetime.datetime.now(datetime.timezone.utc),
        }}
    )
    
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/plan', headers=headers, timeout=600)
    print('Status:', r.status_code)
    try:
        j = r.json()
        print('Full response:')
        print(json.dumps(j, indent=2, default=str)[:3000])
    except:
        print('Raw:', r.text[:2000])

asyncio.run(main())
