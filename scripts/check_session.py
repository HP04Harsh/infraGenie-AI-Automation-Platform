"""Check specific ticket the user is looking at."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    uid = 'bc22a3b5-66a0-442a-ab93-90d6dff42e99'
    
    # Check the specific ticket from logs
    ticket = await db.tickets.find_one({"id": "d78455e3-04e3-4e74-ad1f-561d74c65208"})
    if ticket:
        print(f"ticket_number: {ticket.get('ticket_number')}")
        print(f"servicenow_sys_id: {ticket.get('servicenow_sys_id')}")
        print(f"servicenow_number: {ticket.get('servicenow_number')}")
        print(f"status: {ticket.get('status')}")
        print(f"title: {ticket.get('title')}")
        print(f"resource_name: {ticket.get('resource_name')}")
        print(f"source: {ticket.get('source')}")
        print(f"module_label: {ticket.get('module_label')}")
    else:
        print("Ticket not found - checking recent tickets")
    
    # Check the session
    session = await db.provisioning_sessions.find_one({"id": "546c9e0d-d572-4886-91f1-06094ece7c3e"})
    if session:
        print(f"\nSession status: {session.get('status')}")
        print(f"Module: {session.get('module_key')}")
        print(f"Vars: {session.get('collected_vars', {})}")
        ticket_id = session.get('ticket_id')
        if ticket_id:
            t = await db.tickets.find_one({"id": ticket_id})
            if t:
                print(f"Ticket: {t.get('ticket_number')} SN:{t.get('servicenow_number')} SN-ID:{t.get('servicenow_sys_id')}")
    else:
        print("Session not found")
    
    # Check ServiceNow for recent incidents by this admin
    import httpx
    sn_secret = await db.integration_secrets.find_one({"user_id": uid, "key": "servicenow"})
    sn_int = await db.integrations.find_one({"user_id": uid, "key": "servicenow"})
    if sn_secret and sn_int:
        instance_url = sn_int['fields']['instance_url']
        username = sn_int['fields']['username']
        password = sn_secret['password']
        # Get last 5 incidents by sys_created_on DESC
        r = httpx.get(
            f"{instance_url}/api/now/table/incident?sysparm_limit=5&sysparm_query=ORDERBYDESCsys_created_on&sysparm_fields=number,sys_id,short_description,state,caller_id,watch_list,assignment_group",
            auth=(username, password),
            headers={"Accept": "application/json"},
            timeout=10
        )
        print(f"\n=== Latest 5 SN Incidents ===")
        if r.status_code == 200:
            for inc in r.json().get('result', []):
                print(f"  {inc.get('number')}: {inc.get('short_description')} | state={inc.get('state')} | caller={inc.get('caller_id')} | watch={inc.get('watch_list')}")
        else:
            print(f"Error: {r.status_code} {r.text[:300]}")

asyncio.run(main())
