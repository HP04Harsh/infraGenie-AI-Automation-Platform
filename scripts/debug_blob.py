"""Debug why label isn't appearing in blob path."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    
    # Check the full apply_result for errors
    session = await db.provisioning_sessions.find_one({"id": "78ba9b0e-4cca-4717-9817-3bdf762f1df4"})
    ar = session.get("apply_result", {})
    print("Full apply_result keys:", list(ar.keys()))
    blobs = ar.get("blob_artifacts", {})
    print("blob_artifacts keys:", list(blobs.keys()))
    
    # Check if error key exists
    if "error" in blobs:
        print("ERROR in blob upload:", blobs["error"])
    
    # Log all blob paths
    for k, v in blobs.items():
        print(f"  {k}: {v}")
    
    # Also check if blob path generated correctly
    # Let's check the actual blob container
    import httpx
    tf_storage = await db.tf_storage_configs.find_one({"user_id": "bc22a3b5-66a0-442a-ab93-90d6dff42e99"})
    if tf_storage:
        from azure.storage.blob import BlobServiceClient
        acct = tf_storage["storage_account"]
        key = tf_storage["access_key"]
        container = tf_storage["container"]
        conn = f"DefaultEndpointsProtocol=https;AccountName={acct};AccountKey={key};EndpointSuffix=core.windows.net"
        client2 = BlobServiceClient.from_connection_string(conn)
        cc = client2.get_container_client(container)
        blobs_list = cc.list_blobs(name_starts_with="infragenie/75c3f7fc-74c8-457f-a736-4516b6276c01/")
        print("\nActual blobs in storage:")
        for b in blobs_list:
            print(f"  {b.name}")

asyncio.run(main())
