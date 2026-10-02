import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import ValidationError
from handler import download_handler
from security.rate_limit import check_general_limit


async def media_endpoint(request: Request):
    check_general_limit(request)
    token = request.query_params.get("token", "")
    if not token or len(token) > 4096:
        raise ValidationError()
    return JSONResponse(download_handler.media_info(token))


from main.app import create_app

app = create_app()
