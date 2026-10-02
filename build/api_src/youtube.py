import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import AppError
from core.logger import get_logger
from handler import youtube_handler
from security.rate_limit import check_general_limit

logger = get_logger("api.youtube")


async def youtube_endpoint(request: Request):
    check_general_limit(request)
    try:
        body = await request.json()
    except Exception:
        raise AppError()
    from core.exceptions import ValidationError
    if not isinstance(body, dict):
        raise ValidationError()
    result = await youtube_handler.analyze(body)
    return JSONResponse(result)



