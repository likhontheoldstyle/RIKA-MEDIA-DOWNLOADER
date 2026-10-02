import os

from core import config
from core.logger import get_logger

logger = get_logger("main.startup")


def ensure_directories():
    for path in (
        config.TEMP_DIR,
        os.path.join(config.BASE_DIR, "var", "cache"),
        os.path.join(config.BASE_DIR, "var", "runtime"),
    ):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass


def log_startup():
    logger.info("starting RIKA MEDIA DOWNLOADER env=%s", config.APP_ENV)
    logger.info("mp3 conversion available: %s", config.mp3_available())


def startup():
    ensure_directories()
    log_startup()
