import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.responses import JSONResponse


async def health_endpoint():
    return JSONResponse({"status": "ok"})


from main.app import create_app

app = create_app()
