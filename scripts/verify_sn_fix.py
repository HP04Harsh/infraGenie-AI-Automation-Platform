"""Verify SN ticket has proper caller_id and blob path format."""
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
    
    # Check the latest incident (INC0010033) for proper caller_id
    for num in ['INC0010033', 'INC0010032', 'INC0010028']:
        r = httpx.get(
            f"{instance_url}/api/now/table/incident?sysparm_query=number={num}&sysparm_fields=number,sys_id,short_description,state,caller_id,assigned_to,watch_list",
            auth=auth, headers={"Accept": "application/json"}, timeout=10
        )
        if r.status_code == 200:
            results = r.json().get('result', [])
            if results:
                inc = results[0]
                caller = inc.get('caller_id')
                assignee = inc.get('assigned_to')
                print(f"{num}: caller={caller} assigned_to={assignee} watch={inc.get('watch_list')}")
                # Check if caller is a dict with sys_id (proper) or string (broken)
                if isinstance(caller, dict):
                    print(f"  -> caller sys_id OK: {caller.get('value')}")
                elif caller:
                    print(f"  -> caller is raw string (BROKEN): {caller}")
                else:
                    print(f"  -> no caller set")
                if isinstance(assignee, dict):
                    print(f"  -> assigned_to OK: {assignee.get('value')}")

asyncio.run(main())
