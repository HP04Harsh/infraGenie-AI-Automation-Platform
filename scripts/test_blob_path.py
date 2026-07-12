"""Deploy a small test and check blob path."""
import asyncio, httpx
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    # Login
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    # Create session
    r = httpx.post('http://localhost:8000/api/provisioning/sessions', headers=headers, json={"module_key": "resource-group"}, timeout=10)
    sid = r.json()["id"]
    print(f"Session: {sid}")
    
    # Set vars directly
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    import datetime
    import time
    unique_name = f"rg-blob-test-{int(time.time())}"
    vars_map = {"name": unique_name, "location": "westus2", "tags": {"env": "test"}}
    await db.provisioning_sessions.update_one(
        {"id": sid},
        {"$set": {"collected_vars": vars_map, "missing_vars": [], "status": "ready",
                   "updated_at": datetime.datetime.now(datetime.timezone.utc)}}
    )
    
    # Plan
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/plan', headers=headers, timeout=600)
    print(f"Plan: {r.status_code}")
    
    # Approve
    r = httpx.post(f'http://localhost:8000/api/provisioning/sessions/{sid}/approve', headers=headers, json={"decision": "approved"}, timeout=600)
    print(f"Approve: {r.status_code}")
    
    # Wait for completion
    for i in range(60):
        r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
        s = r.json()
        if s.get("status") in ("completed", "failed"):
            print(f"Status: {s['status']}")
            break
        await asyncio.sleep(10)
    
    # Check blob artifacts path
    s = await db.provisioning_sessions.find_one({"id": sid})
    ar = s.get("apply_result", {})
    blobs = ar.get("blob_artifacts", {})
    print(f"\nBlob artifacts:")
    for name, path in blobs.items():
        print(f"  {name}: {path}")

asyncio.run(main())
