"""Wait for deployment to complete and show results."""
import asyncio, httpx, time, json

async def main():
    r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'guest@infragenie.io','password':'Guest@321'}, timeout=10)
    token = r.cookies.get('ig_token')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    sid = '749ba891-6060-477d-b9a4-4e5d97da2c5a'
    
    # Poll until done
    for i in range(60):
        r = httpx.get(f'http://localhost:8000/api/provisioning/sessions/{sid}', headers=headers, timeout=10)
        s = r.json()
        status = s.get('status')
        plan = s.get('plan', {})
        logs = plan.get('terraform_log', '')
        print(f"Status: {status}")
        
        if status in ('deployed', 'failed', 'completed'):
            print(f"Final status: {status}")
            
            # Show outputs
            outputs = plan.get('outputs', [])
            if outputs:
                for o in outputs:
                    print(f"  Output: {o}")
            
            # Show last log lines
            if logs:
                lines = logs.split('\n')
                for line in lines[-30:]:
                    print(f"  {line}")
            break
        
        await asyncio.sleep(10)

asyncio.run(main())
