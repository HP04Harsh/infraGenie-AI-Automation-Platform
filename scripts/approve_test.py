"""Approve and wait."""
import asyncio, httpx

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    sid = '78ba9b0e-4cca-4717-9817-3bdf762f1df4'
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/approve', headers=headers, json={"decision": "approved"}, timeout=600)
    print(f"Approve: {r.status_code}")
    
    for i in range(60):
        r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
        s = r.json()
        if s.get("status") in ("completed", "failed"):
            print(f"Status: {s['status']}")
            ar = s.get('apply_result', {})
            blobs = ar.get('blob_artifacts', {})
            print("Blob paths:")
            for name, path in blobs.items():
                print(f"  {name}: {path}")
            break
        await asyncio.sleep(10)

asyncio.run(main())
