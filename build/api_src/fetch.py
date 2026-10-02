import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import ValidationError
from core.logger import get_logger
from handler import fetch_handler
from security.rate_limit import check_rate_limit

logger = get_logger("api.fetch")


async def fetch_endpoint(request: Request):
    check_rate_limit(request)
    try:
        body = await request.json()
    except Exception:
        raise ValidationError()
    result = await fetch_handler.universal_analyze(body)
    return JSONResponse(result)



