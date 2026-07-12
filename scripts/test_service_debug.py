import sys, json, asyncio, os, logging
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "/app")
from infracost_service import _run_infracost
from pathlib import Path

async def main():
    print(f"INFRACOST_BIN exists: {os.path.exists('/usr/local/bin/infracost')}")
    print(f"INFRACOST_API_KEY: {os.environ.get('INFRACOST_API_KEY', 'NOT SET')[:20]}...")
    print(f"CWD: {os.getcwd()}")
    print(f"Dir exists: {Path('.').exists()}")
    result = await _run_infracost(
        ["scan", "--json", "--no-color", "."],
        Path(".")
    )
    print("RESULT:", json.dumps(result, indent=2) if result else None)

asyncio.run(main())
