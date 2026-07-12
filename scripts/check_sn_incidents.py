"""Check if our ServiceNow incidents actually exist."""
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
    
    # Query for our specific incident numbers
    our_numbers = ['INC0010021', 'INC0010022', 'INC0010023', 'INC0010024', 'INC0010025',
                   'INC0010026', 'INC0010027', 'INC0010028', 'INC0010029', 'INC0010030',
                   'INC0010031', 'INC0010032']
    
    for num in our_numbers:
        r = httpx.get(
            f"{instance_url}/api/now/table/incident?sysparm_query=number={num}&sysparm_fields=number,sys_id,short_description,state,caller_id,watch_list",
            auth=auth, headers={"Accept": "application/json"}, timeout=10
        )
        if r.status_code == 200:
            results = r.json().get('result', [])
            if results:
                inc = results[0]
                print(f"FOUND {num}: desc={inc.get('short_description')} state={inc.get('state')} caller={inc.get('caller_id')} watch={inc.get('watch_list')}")
            else:
                print(f"MISSING {num}: not found in ServiceNow")
        else:
            print(f"ERROR {num}: {r.status_code} {r.text[:200]}")
    
    # Also try with sysparm_limit=100 to see all
    print("\n=== ALL INCIDENTS (limit 100) ===")
    r = httpx.get(
        f"{instance_url}/api/now/table/incident?sysparm_limit=100&sysparm_fields=number,short_description,state",
        auth=auth, headers={"Accept": "application/json"}, timeout=10
    )
    if r.status_code == 200:
        for inc in r.json().get('result', []):
            print(f"  {inc.get('number')}: {inc.get('short_description')} (state={inc.get('state')})")

asyncio.run(main())
