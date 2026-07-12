"""Debug ServiceNow ticket sync for a specific ticket."""
import asyncio, httpx
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    uid = 'bc22a3b5-66a0-442a-ab93-90d6dff42e99'
    
    # Check the specific ticket
    ticket_id = 'd78455e3-04e3-4e74-ad1f-561d74c65208'
    ticket = await db.tickets.find_one({"id": ticket_id})
    if ticket:
        print("=== TICKET ===")
        print(f"ticket_number: {ticket.get('ticket_number')}")
        print(f"servicenow_sys_id: {ticket.get('servicenow_sys_id')}")
        print(f"servicenow_number: {ticket.get('servicenow_number')}")
        print(f"status: {ticket.get('status')}")
        print(f"title: {ticket.get('title')}")
        print(f"source: {ticket.get('source')}")
    else:
        print(f"Ticket {ticket_id} not found")
    
    # Check all tickets with ServiceNow info
    print("\n=== ALL TICKETS WITH SN INFO ===")
    cursor = db.tickets.find({"user_id": uid}).sort("created_at", -1).limit(20)
    async for t in cursor:
        sn_num = t.get('servicenow_number') or 'N/A'
        sn_sys = t.get('servicenow_sys_id') or 'N/A'
        title = t.get('title') or t.get('resource_name') or t.get('deployment_name') or '?'
        source = t.get('source') or t.get('module_key') or 'provisioning'
        print(f"  {t.get('ticket_number')}: {title} | SN: {sn_num} ({sn_sys}) | {source}")
    
    # Check ServiceNow directly for all incidents
    print("\n=== DIRECT SN CHECK ===")
    sn_secret = await db.integration_secrets.find_one({"user_id": uid, "key": "servicenow"})
    sn_int = await db.integrations.find_one({"user_id": uid, "key": "servicenow"})
    if sn_secret and sn_int:
        instance_url = sn_int['fields']['instance_url']
        username = sn_int['fields']['username']
        password = sn_secret['password']
        # Get recent incidents
        r = httpx.get(
            f"{instance_url}/api/now/table/incident?sysparm_limit=10&sysparm_fields=number,sys_id,short_description,state,watch_list,caller_id",
            auth=(username, password),
            headers={"Accept": "application/json"},
            timeout=10
        )
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            results = r.json().get('result', [])
            print(f"Found {len(results)} incidents:")
            for inc in results:
                print(f"  {inc.get('number')}: {inc.get('short_description')} | state={inc.get('state')} | watch={inc.get('watch_list')} | caller={inc.get('caller_id')}")
        else:
            print(f"Error: {r.text[:500]}")
    else:
        print("ServiceNow not configured")

asyncio.run(main())
