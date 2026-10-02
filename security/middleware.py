import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core import config
from core.constants import GENERIC_ERROR
from core.logger import get_logger
from security.headers import security_headers
from security import security_config as scfg

logger = get_logger("security.middleware")

_abuse_hits = {}


def _abuse_check(ip):
    if not scfg.ENABLE_ABUSE_BLOCK:
        return False
    now = time.time()
    entry = _abuse_hits.get(ip)
    if entry and entry.get("blocked_until", 0) > now:
        return True
    window_start = now - 60
    times = [t for t in (entry.get("times") if entry else []) if t >= window_start]
    times.append(now)
    blocked = len(times) >= scfg.ABUSE_THRESHOLD
    _abuse_hits[ip] = {
        "times": times[-scfg.ABUSE_THRESHOLD:],
        "blocked_until": now + scfg.ABUSE_BLOCK_SECONDS if blocked else 0,
    }
    if len(_abuse_hits) > 10000:
        _abuse_hits.clear()
    return blocked


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > config.MAX_REQUEST_SIZE:
                    return JSONResponse(
                        {"success": False, "error": "Request too large."},
                        status_code=413,
                        headers=security_headers(),
                    )
            except ValueError:
                pass
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            try:
                ip = request.client.host if request.client else "unknown"
            except Exception:
                ip = "unknown"
        if _abuse_check(ip):
            logger.warning("abuse block ip=%s", ip)
            return JSONResponse(
                {"success": False, "error": "Too many requests. Please try again later."},
                status_code=429,
                headers=security_headers(),
            )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error")
            return JSONResponse(
                {"success": False, "error": GENERIC_ERROR},
                status_code=500,
                headers=security_headers(),
            )
        for key, value in security_headers().items():
            response.headers[key] = value
        return response
