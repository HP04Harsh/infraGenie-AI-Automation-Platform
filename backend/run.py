"""Startup script — applies OpenAPI patch before loading the FastAPI app, then
runs uvicorn. Used by the Docker CMD to avoid modifying server.py."""
import patch_openapi  # noqa: F401  (must be imported before server)

import uvicorn
from server import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
