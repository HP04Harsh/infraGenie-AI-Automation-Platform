"""Check deployment runtime path and terraform state."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['infragenie']
    s = await db.provisioning_sessions.find_one({'id': '749ba891-6060-477d-b9a4-4e5d97da2c5a'})
    plan = s.get('plan', {})
    runtime_path = plan.get('runtime_path', '')
    deployment_id = plan.get('deployment_id', '')
    print(f'runtime_path: {runtime_path}')
    print(f'deployment_id: {deployment_id}')
    
    if runtime_path:
        import subprocess, os
        # Check state
        state_file = os.path.join(runtime_path, 'terraform.tfstate')
        if os.path.exists(state_file):
            print('state file exists')
        else:
            print('no state file')
        
        # Run terraform output
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            cwd=runtime_path,
            capture_output=True, text=True, timeout=30
        )
        print(f'terraform output exit: {result.returncode}')
        if result.returncode == 0:
            print('Outputs:', result.stdout[:2000])
        else:
            print('Stderr:', result.stderr[:1000])

asyncio.run(main())
