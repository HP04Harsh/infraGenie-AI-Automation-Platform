"""Check ServiceNow for the INC0010028 ticket and blob uploads."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    uid = 'bc22a3b5-66a0-442a-ab93-90d6dff42e99'
    
    # Check blob artifacts in ticket's apply_result
    ticket = await db.tickets.find_one({"session_id": "749ba891-6060-477d-b9a4-4e5d97da2c5a"})
    
    # Get the full apply_result
    apply_result = ticket.get('apply_result', {})
    print("=== Apply Result ===")
    blob_artifacts = apply_result.get('blob_artifacts', {})
    print(f"blob_artifacts: {blob_artifacts}")
    print(f"outputs: {apply_result.get('outputs', {})}")
    print(f"status: {apply_result.get('status')}")
    
    # Check ServiceNow by making a test call
    print("\n=== Checking ServiceNow for INC0010028 ===")
    sn_secret = await db.integration_secrets.find_one({"user_id": uid, "key": "servicenow"})
    sn_int = await db.integrations.find_one({"user_id": uid, "key": "servicenow"})
    if sn_secret and sn_int:
        import httpx
        instance_url = sn_int['fields']['instance_url']
        username = sn_int['fields']['username']
        password = sn_secret['password']
        print(f"Instance: {instance_url}, User: {username}")
        # Check if ticket exists
        r = httpx.get(
            f"{instance_url}/api/now/table/incident?sysparm_query=number=INC0010028&sysparm_fields=number,sys_id,short_description,state",
            auth=(username, password),
            headers={"Accept": "application/json"},
            timeout=10
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Results: {data.get('result', [])}")
        else:
            print(f"Error: {r.text[:500]}")
    else:
        print("ServiceNow not fully configured")

asyncio.run(main())
