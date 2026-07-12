"""Check MongoDB configs for storage + servicenow."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    
    uid = 'bc22a3b5-66a0-442a-ab93-90d6dff42e99'
    
    # Check tf_storage_configs
    tf_storage = await db.tf_storage_configs.find_one({"user_id": uid})
    print("=== TF_STORAGE_CONFIGS ===")
    if tf_storage:
        print({k: v for k, v in tf_storage.items() if k != '_id'})
    else:
        print("NONE - not configured")
    
    # Check ServiceNow integration_secrets
    sn_secret = await db.integration_secrets.find_one({"user_id": uid, "key": "servicenow"})
    print("\n=== SERVICENOW SECRET ===")
    if sn_secret:
        print({k: ('***' if k in ('value','password','api_key') else v) for k, v in sn_secret.items() if k != '_id'})
    else:
        print("NONE - not configured")
    
    # Check ServiceNow integration
    sn_int = await db.integrations.find_one({"user_id": uid, "key": "servicenow"})
    print("\n=== SERVICENOW INTEGRATION ===")
    if sn_int:
        print({k: v for k, v in sn_int.items() if k != '_id'})
    else:
        print("NONE - not configured")
    
    # Check the ticket created for session 749ba891
    ticket = await db.tickets.find_one({"session_id": "749ba891-6060-477d-b9a4-4e5d97da2c5a"})
    print("\n=== TICKET ===")
    if ticket:
        d = {k: v for k, v in ticket.items() if k != '_id'}
        d.pop('apply_result', None)
        d.pop('logs', None)
        print(d)
        print("servicenow_sys_id:", ticket.get('servicenow_sys_id'))
        print("servicenow_number:", ticket.get('servicenow_number'))
    else:
        print("NONE - no ticket found")
    
    # Check all integration secrets keys
    print("\n=== ALL INTEGRATION SECRETS ===")
    cursor = db.integration_secrets.find({"user_id": uid})
    async for doc in cursor:
        print(doc.get('key'), list(doc.keys()))

asyncio.run(main())
