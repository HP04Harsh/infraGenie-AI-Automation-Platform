"""Check actual apply_result from deployment."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    
    # Check the session for this deployment
    session = await db.provisioning_sessions.find_one({"id": "78ba9b0e-4cca-4717-9817-3bdf762f1df4"})
    if session:
        ar = session.get("apply_result", {})
        print(f"apply_result exists: {bool(ar)}")
        blobs = ar.get("blob_artifacts", {})
        print(f"blob_artifacts: {blobs}")
        
        # Check vars map
        vars_map = session.get("collected_vars", {})
        print(f"vars_map: {vars_map}")
        print(f"name var: {vars_map.get('name', '')}")
    
    # Also check the ticket for this session
    ticket = await db.tickets.find_one({"session_id": "78ba9b0e-4cca-4717-9817-3bdf762f1df4"})
    if ticket:
        ar = ticket.get("apply_result", {})
        blobs = ar.get("blob_artifacts", {})
        print(f"\nTicket blob_artifacts: {blobs}")

asyncio.run(main())
