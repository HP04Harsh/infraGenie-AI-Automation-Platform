"""Debug plan failure."""
import asyncio, httpx

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    sid = '78ba9b0e-4cca-4717-9817-3bdf762f1df4'
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/plan', headers=headers, timeout=600)
    print(f"Plan status: {r.status_code}")
    print(f"Plan body: {r.text[:1000]}")
    
    # Check session
    r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
    s = r.json()
    print(f"\nSession status: {s.get('status')}")
    print(f"Missing vars: {s.get('missing_vars')}")

asyncio.run(main())
