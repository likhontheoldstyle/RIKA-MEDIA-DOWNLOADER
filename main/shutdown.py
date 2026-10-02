from core import utils
from core.logger import get_logger

logger = get_logger("main.shutdown")

_cache_ref = None


def register_cache(cache):
    global _cache_ref
    _cache_ref = cache


def shutdown():
    try:
        if _cache_ref is not None:
            _cache_ref.clear()
    except Exception:
        pass
    logger.info("shutdown complete")
