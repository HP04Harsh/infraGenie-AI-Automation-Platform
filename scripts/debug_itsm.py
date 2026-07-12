"""Debug itsm chat."""
import asyncio, httpx

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    r = httpx.post('http://localhost:8000/api/itsm/chat', headers=headers, json={"message": "list my tickets"}, timeout=60)
    print('Status:', r.status_code)
    print('Body:', r.text[:1000])

asyncio.run(main())
