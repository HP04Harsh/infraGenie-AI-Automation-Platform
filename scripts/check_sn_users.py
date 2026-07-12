"""Check ServiceNow sys_user table for existing users."""
import asyncio, httpx
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    uid = 'bc22a3b5-66a0-442a-ab93-90d6dff42e99'
    
    sn_secret = await db.integration_secrets.find_one({"user_id": uid, "key": "servicenow"})
    sn_int = await db.integrations.find_one({"user_id": uid, "key": "servicenow"})
    if not (sn_secret and sn_int):
        print("ServiceNow not configured")
        return
    
    instance_url = sn_int['fields']['instance_url']
    username = sn_int['fields']['username']
    password = sn_secret['password']
    auth = (username, password)
    
    # Get admin user info
    r = httpx.get(
        f"{instance_url}/api/now/table/sys_user?sysparm_query=user_name={username}&sysparm_fields=sys_id,email,user_name,name",
        auth=auth, headers={"Accept": "application/json"}, timeout=10
    )
    if r.status_code == 200:
        results = r.json().get('result', [])
        print("=== Admin user ===")
        for u in results:
            print(f"  sys_id={u['sys_id']} name={u.get('name')} email={u.get('email')} username={u.get('user_name')}")
    
    # Check if guest@infragenie.io exists
    r = httpx.get(
        f"{instance_url}/api/now/table/sys_user?sysparm_query=email=guest@infragenie.io&sysparm_fields=sys_id,email,user_name,name",
        auth=auth, headers={"Accept": "application/json"}, timeout=10
    )
    if r.status_code == 200:
        results = r.json().get('result', [])
        print(f"\n=== guest@infragenie.io: {len(results)} users ===")
        for u in results:
            print(f"  sys_id={u['sys_id']} name={u.get('name')} email={u.get('email')}")
        if not results:
            print("  User NOT found in ServiceNow")
    
    # Check if harshpardhi477@gmail.com exists
    r = httpx.get(
        f"{instance_url}/api/now/table/sys_user?sysparm_query=email=harshpardhi477@gmail.com&sysparm_fields=sys_id,email,user_name,name",
        auth=auth, headers={"Accept": "application/json"}, timeout=10
    )
    if r.status_code == 200:
        results = r.json().get('result', [])
        print(f"\n=== harshpardhi477@gmail.com: {len(results)} users ===")
        for u in results:
            print(f"  sys_id={u['sys_id']} name={u.get('name')} email={u.get('email')}")
        if not results:
            print("  User NOT found in ServiceNow")
    
    # List all sys_users
    r = httpx.get(
        f"{instance_url}/api/now/table/sys_user?sysparm_limit=20&sysparm_fields=sys_id,email,user_name,name",
        auth=auth, headers={"Accept": "application/json"}, timeout=10
    )
    if r.status_code == 200:
        print(f"\n=== All sys_users (first 20) ===")
        for u in r.json().get('result', []):
            print(f"  sys_id={u['sys_id']} name={u.get('name','?')} email={u.get('email','?')} username={u.get('user_name','?')}")

asyncio.run(main())
