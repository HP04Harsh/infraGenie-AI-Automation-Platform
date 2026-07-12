import sys, json, asyncio
sys.path.insert(0, "/app")
from infracost_service import estimate_with_infracost
from pathlib import Path

result = asyncio.run(estimate_with_infracost(Path("."), "test", {}))
print(json.dumps(result, indent=2))
