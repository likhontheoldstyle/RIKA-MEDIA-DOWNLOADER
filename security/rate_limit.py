import time

from core import config
from core.exceptions import RateLimitExceeded


class SlidingWindowLimiter:
    def __init__(self, max_requests, window_seconds=60, max_buckets=5000):
        self.max_requests = max_requests
        self.window = window_seconds
        self.max_buckets = max_buckets
        self._hits = {}

    def _prune(self, now):
        if len(self._hits) > self.max_buckets:
            cutoff = now - self.window
            stale = [key for key, times in self._hits.items() if not times or times[-1] < cutoff]
            for key in stale[: len(stale) // 2 + 1]:
                self._hits.pop(key, None)

    def check(self, key):
        now = time.time()
        self._prune(now)
        times = self._hits.get(key) or []
        cutoff = now - self.window
        times = [t for t in times if t >= cutoff]
        if len(times) >= self.max_requests:
            raise RateLimitExceeded()
        times.append(now)
        self._hits[key] = times


general_limiter = SlidingWindowLimiter(config.RATE_LIMIT, 60)
mp3_limiter = SlidingWindowLimiter(config.MP3_RATE_LIMIT, 60)


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()[:64]
    try:
        return (request.client.host if request.client else "unknown")[:64]
    except Exception:
        return "unknown"


def check_general_limit(request):
    general_limiter.check("general:" + client_ip(request))


def check_mp3_limit(request):
    mp3_limiter.check("mp3:" + client_ip(request))
