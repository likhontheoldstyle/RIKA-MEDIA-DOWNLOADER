from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.constants import GENERIC_ERROR
from core.exceptions import AppError
from core.logger import get_logger
from security.middleware import SecurityMiddleware

logger = get_logger("main.app")


def create_app():
    app = FastAPI(title="RIKA MEDIA DOWNLOADER", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityMiddleware)

    from api.youtube import youtube_endpoint
    from api.download import download_endpoint
    from api.media import media_endpoint
    from api.mp3 import mp3_endpoint
    from api.health import health_endpoint

    app.post("/api/youtube")(youtube_endpoint)
    app.get("/api/download")(download_endpoint)
    app.get("/api/media")(media_endpoint)
    app.post("/api/mp3")(mp3_endpoint)
    app.get("/api/health")(health_endpoint)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.warning("app error %s: %s", type(exc).__name__, exc.safe_message)
        return JSONResponse(
            {"success": False, "error": exc.safe_message},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("unhandled exception")
        return JSONResponse(
            {"success": False, "error": GENERIC_ERROR},
            status_code=500,
        )

    return app
