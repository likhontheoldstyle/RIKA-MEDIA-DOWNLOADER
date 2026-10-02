import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask

from core import utils
from core.exceptions import ConversionUnavailable, ValidationError
from core.logger import get_logger
from handler import mp3_handler
from security.rate_limit import check_mp3_limit

logger = get_logger("api.mp3")


def _file_iterator(path):
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            yield chunk


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
    if not mp3_handler_available():
        raise ConversionUnavailable()
    result = await mp3_handler.convert(token)
    if result["type"] == "redirect":
        return RedirectResponse(url=result["url"], status_code=302)
    task = BackgroundTask(utils.cleanup_dir, result["tmpdir"])
    headers = {
        "Content-Disposition": 'attachment; filename="%s"' % result["filename"].replace('"', ""),
    }
    return StreamingResponse(
        _file_iterator(result["path"]),
        media_type="audio/mpeg",
        headers=headers,
        background=task,
    )


def mp3_handler_available():
    from core import config
    return config.mp3_available()


from main.app import create_app

app = create_app()
