import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from core import utils
from core.exceptions import ConversionUnavailable, ValidationError
from core.logger import get_logger
from handler import mp3_handler
from handler.download_handler import resolve_token
from security.rate_limit import check_mp3_limit

logger = get_logger("api.mp3")


async def mp3_endpoint(request: Request):
    check_mp3_limit(request)
    try:
        body = await request.json()
    except Exception:
        raise ValidationError()
    if not isinstance(body, dict):
        raise ValidationError()
    token = body.get("token", "")
    if not token or not isinstance(token, str):
        raise ValidationError()
    if not mp3_handler.mp3_handler_available():
        raise ConversionUnavailable()
    payload = resolve_token(token)
    title = payload.get("t", "audio")
    filename = utils.safe_filename("%s_192kbps" % title, "mp3")
    headers = {
        "Content-Disposition": 'attachment; filename="%s"' % filename.replace('"', ""),
    }
    return StreamingResponse(
        mp3_handler.mp3_stream(token),
        media_type="audio/mpeg",
        headers=headers,
    )



