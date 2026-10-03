from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

VIDEO_EXTENSIONS = {"mp4", "webm", "mkv", "3gp"}

AUDIO_EXTENSIONS = {"m4a", "weba", "webm", "aac", "mp3", "opus", "ogg"}

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

DOWNLOAD_HOST_EXACT = {
    "redirector.googlevideo.com",
}

DOWNLOAD_HOST_SUFFIXES = (
    ".googlevideo.com",
    ".fbcdn.net",
)

THUMBNAIL_HOST_SUFFIXES = (
    ".ytimg.com",
    ".youtube.com",
)

BLOCKED_SCHEMES = {
    "file",
    "ftp",
    "gopher",
    "data",
    "javascript",
    "jar",
    "ldap",
    "dict",
}

BLOCKED_HOSTS = {
    "localhost",
}

QUALITY_RANK = {
    "4320p": 4320,
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "240p": 240,
    "144p": 144,
}

K_LABELS = {
    "8": "4320p",
    "4": "2160p",
    "2": "1440p",
}

UPSTREAM_TIMEOUT = 25.0
COBALT_TIMEOUT = 30.0
DOWNLOAD_TIMEOUT = 60.0
FFMPEG_TIMEOUT = 180.0

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

GENERIC_ERROR = "Unable to process this request."



class AppError(Exception):
    status_code = 500
    safe_message = GENERIC_ERROR


class InvalidURL(AppError):
    status_code = 400
    safe_message = "Invalid YouTube URL."


class UnsupportedPlatform(AppError):
    status_code = 400
    safe_message = "This platform is not supported. Try YouTube, TikTok, Instagram, Facebook or X."


class APIError(AppError):
    status_code = 502
    safe_message = "Unable to process this video right now."


class MediaNotFound(AppError):
    status_code = 404
    safe_message = "No media found for this video."


class MediaExpired(AppError):
    status_code = 410
    safe_message = "This download link has expired. Please analyze the video again."


class ConversionError(AppError):
    status_code = 500
    safe_message = "MP3 conversion failed. Please try again later."


class ConversionUnavailable(AppError):
    status_code = 503
    safe_message = "MP3 conversion is temporarily unavailable."


class RateLimitExceeded(AppError):
    status_code = 429
    safe_message = "Rate limit exceeded. Please slow down and try again."


class ValidationError(AppError):
    status_code = 400
    safe_message = "Invalid request."

import logging
import os
import re


_MASK_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s&;]{8,})"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(cookie\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(sig(nature)?=[^&\s]{16,})"),
    re.compile(r"(?i)(pot=[^&\s]{16,})"),
]


def mask_secrets(text):
    if not isinstance(text, str):
        text = str(text)
    masked = text
    for pattern in _MASK_PATTERNS:
        masked = pattern.sub(lambda m: m.group(1) + "***", masked)
    for name in ("SECRET_KEY", "CONVERTER_API_KEY", "BOT_TOKEN"):
        value = os.environ.get(name, "")
        if value and len(value) > 4 and value in masked:
            masked = masked.replace(value, "***")
    return masked


class SecretMaskFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = mask_secrets(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler.addFilter(SecretMaskFilter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger

import functools
import os
import shutil
import tempfile


def _env(name, default=""):
    value = os.environ.get(name, default)
    return value if isinstance(value, str) else default


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


APP_ENV = _env("APP_ENV", "production")
SECRET_KEY = "rx_zrNY09MxlMwEn-43ZEQjaCp7zsMrlI07Ojrj2oWjpBlZDxTRG6NL7EK9TmP89"
YTDL_API_URL = _env("YTDL_API_URL", "https://api.ytultra.com/ikool/youtube/download")
COBALT_API_URL = _env("COBALT_API_URL", "")
FFMPEG_PATH = _env("FFMPEG_PATH", "")
CONVERTER_URL = _env("CONVERTER_URL", "")
CONVERTER_API_KEY = _env("CONVERTER_API_KEY", "")
RATE_LIMIT = _env_int("RATE_LIMIT", 10)
MP3_RATE_LIMIT = _env_int("MP3_RATE_LIMIT", 3)
CACHE_TTL = _env_int("CACHE_TTL", 600)
TOKEN_TTL = _env_int("TOKEN_TTL", 2700)
MAX_REQUEST_SIZE = _env_int("MAX_REQUEST_SIZE", 1048576)
MAX_URL_LENGTH = _env_int("MAX_URL_LENGTH", 2048)
MP3_BITRATE = _env("MP3_BITRATE", "192k")
MP3_MAX_SOURCE_BYTES = _env_int("MP3_MAX_SOURCE_BYTES", 262144000)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_temp_dir():
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return tempfile.gettempdir()
    return os.path.join(BASE_DIR, "var", "temp")


TEMP_DIR = _env("TEMP_DIR", "") or _default_temp_dir()


@functools.lru_cache(maxsize=1)
def resolve_ffmpeg():
    if FFMPEG_PATH:
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            return FFMPEG_PATH
        return ""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        return ""
    return ""


def local_converter_available():
    return bool(resolve_ffmpeg())


def remote_converter_available():
    return bool(CONVERTER_URL)


def mp3_available():
    return bool(local_converter_available() or remote_converter_available())

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import time

from cryptography.fernet import Fernet, InvalidToken



_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MULTI_SEP = re.compile(r"[._-]+")
_SIZE_RE = re.compile(r"([\d.]+)\s*([KMGT]B)", re.IGNORECASE)


def _fernet():
    raw = SECRET_KEY.encode("utf-8")
    try:
        key = base64.urlsafe_b64encode(raw)
        return Fernet(key)
    except Exception:
        digest = hashlib.sha256(raw).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def issue_token(payload):
    data = dict(payload)
    data["exp"] = int(time.time()) + TOKEN_TTL
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def verify_token(token):
    if not token or not isinstance(token, str) or len(token) > 4096:
        return None
    try:
        raw = _fernet().decrypt(token.encode("utf-8"), ttl=TOKEN_TTL + 300)
        data = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, KeyError):
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    if not data.get("u"):
        return None
    return data


def new_id():
    return secrets.token_urlsafe(16)


def format_size(num_bytes):
    if num_bytes is None:
        return None
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return None
    if size < 0:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    if index == 0:
        return "%d %s" % (size, units[index])
    return "%.2f %s" % (size, units[index])


def parse_size_text(text):
    if not text or not isinstance(text, str):
        return None
    match = _SIZE_RE.search(text)
    if not match:
        return None
    multipliers = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
    try:
        return int(float(match.group(1)) * multipliers[match.group(2).upper()])
    except (ValueError, KeyError):
        return None


def safe_filename(name, extension=""):
    base = _SAFE_CHARS.sub("_", str(name or "media"))
    base = _MULTI_SEP.sub("_", base).strip("._-")
    if not base:
        base = "media"
    base = base[:120]
    ext = re.sub(r"[^A-Za-z0-9]", "", str(extension or ""))[:10]
    if ext:
        return "%s.%s" % (base, ext.lower())
    return base


def quality_rank(quality):
    if not quality:
        return -1
    text = str(quality).strip().lower()
    if text in QUALITY_RANK:
        return QUALITY_RANK[text]
    match = re.match(r"(\d{3,4})\s*p", text)
    if match:
        return int(match.group(1))
    return -1


def cleanup_path(path):
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def cleanup_dir(path):
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


class TTLCache:
    def __init__(self, ttl=600, max_items=200):
        self._ttl = ttl
        self._max_items = max_items
        self._store = {}

    def get(self, key):
        item = self._store.get(key)
        if not item:
            return None
        value, expires = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key, value):
        if len(self._store) >= self._max_items:
            oldest = min(self._store.items(), key=lambda kv: kv[1][1])[0]
            self._store.pop(oldest, None)
        self._store[key] = (value, time.time() + self._ttl)

    def clear(self):
        self._store.clear()

import os

APP_NAME = "RIKA MEDIA DOWNLOADER"

TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))

MIN_REQUEST_INTERVAL = float(os.environ.get("MIN_REQUEST_INTERVAL", "0"))

ENABLE_ABUSE_BLOCK = os.environ.get("ENABLE_ABUSE_BLOCK", "1") == "1"

ABUSE_THRESHOLD = int(os.environ.get("ABUSE_THRESHOLD", "60"))

ABUSE_BLOCK_SECONDS = int(os.environ.get("ABUSE_BLOCK_SECONDS", "600"))

CSP = (
    "default-src 'self'; "
    "img-src 'self' https: data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def security_headers():
    return {
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }

import ipaddress
import re
import socket
from urllib.parse import urlparse



_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _host_allowed_for_youtube(host):
    return host in YOUTUBE_HOSTS


def _reject_dangerous_target(host):
    if not host:
        raise InvalidURL()
    lowered = host.lower()
    if lowered in BLOCKED_HOSTS:
        raise InvalidURL()
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        ip = None
    if ip is not None:
        raise InvalidURL()
    if lowered.endswith(".local") or lowered.endswith(".internal"):
        raise InvalidURL()


def extract_video_id(url):
    if not url or not isinstance(url, str):
        raise InvalidURL()
    text = url.strip()
    if len(text) > MAX_URL_LENGTH:
        raise InvalidURL()
    try:
        parsed = urlparse(text)
    except ValueError:
        raise InvalidURL()
    if parsed.scheme not in ("http", "https"):
        raise InvalidURL()
    host = (parsed.hostname or "").lower()
    if not _host_allowed_for_youtube(host):
        raise UnsupportedPlatform()
    _reject_dangerous_target(host)
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
        if _VIDEO_ID_RE.match(candidate or ""):
            return candidate
        raise InvalidURL()
    query = {}
    for part in parsed.query.split("&"):
        if "=" in part:
            key, _, value = part.partition("=")
            query[key] = value
    candidate = query.get("v", "")
    if _VIDEO_ID_RE.match(candidate or ""):
        return candidate
    for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
        if parsed.path.startswith(prefix):
            candidate = parsed.path[len(prefix):].split("/")[0].split("?")[0]
            if _VIDEO_ID_RE.match(candidate or ""):
                return candidate
    raise InvalidURL()


def validate_youtube_url(url):
    video_id = extract_video_id(url)
    return video_id


def validate_media_url(url):
    if not url or not isinstance(url, str):
        raise InvalidURL()
    text = url.strip()
    if len(text) > MAX_URL_LENGTH:
        raise InvalidURL()
    try:
        parsed = urlparse(text)
    except ValueError:
        raise InvalidURL()
    if parsed.scheme not in ("http", "https"):
        raise InvalidURL()
    host = (parsed.hostname or "").lower()
    if not host:
        raise InvalidURL()
    _reject_dangerous_target(host)
    return text


def _host_allowed_for_download(host):
    lowered = host.lower()
    if lowered in DOWNLOAD_HOST_EXACT:
        return True
    return any(lowered.endswith(suffix) for suffix in DOWNLOAD_HOST_SUFFIXES)


def validate_download_url(url):
    if not url or not isinstance(url, str) or len(url) > 8192:
        raise ValidationError()
    try:
        parsed = urlparse(url)
    except ValueError:
        raise ValidationError()
    if parsed.scheme != "https":
        raise ValidationError()
    if parsed.username or parsed.password:
        raise ValidationError()
    host = (parsed.hostname or "").lower()
    if not host or not _host_allowed_for_download(host):
        raise ValidationError()
    _reject_dangerous_target(host)
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValidationError()
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValidationError()
    return url


def validate_cobalt_download_url(url, instance_host):
    if not url or not isinstance(url, str) or len(url) > 8192:
        raise ValidationError()
    if not instance_host or not isinstance(instance_host, str):
        raise ValidationError()
    try:
        parsed = urlparse(url)
    except ValueError:
        raise ValidationError()
    if parsed.scheme != "https":
        raise ValidationError()
    if parsed.username or parsed.password:
        raise ValidationError()
    host = (parsed.hostname or "").lower()
    if host != instance_host.lower():
        raise ValidationError()
    _reject_dangerous_target(host)
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValidationError()
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValidationError()
    return url


def validate_thumbnail_url(url):
    if not url or not isinstance(url, str) or len(url) > 2048:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme != "https":
        return ""
    host = (parsed.hostname or "").lower()
    if not any(host.endswith(suffix) for suffix in THUMBNAIL_HOST_SUFFIXES):
        return ""
    return url


def validate_json_body(body, max_keys=10):
    if not isinstance(body, dict):
        raise ValidationError()
    if len(body) > max_keys:
        raise ValidationError()
    return body

import time



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


general_limiter = SlidingWindowLimiter(RATE_LIMIT, 60)
mp3_limiter = SlidingWindowLimiter(MP3_RATE_LIMIT, 60)


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

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


logger = get_logger("security.middleware")

_abuse_hits = {}


def _abuse_check(ip):
    if not ENABLE_ABUSE_BLOCK:
        return False
    now = time.time()
    entry = _abuse_hits.get(ip)
    if entry and entry.get("blocked_until", 0) > now:
        return True
    window_start = now - 60
    times = [t for t in (entry.get("times") if entry else []) if t >= window_start]
    times.append(now)
    blocked = len(times) >= ABUSE_THRESHOLD
    _abuse_hits[ip] = {
        "times": times[-ABUSE_THRESHOLD:],
        "blocked_until": now + ABUSE_BLOCK_SECONDS if blocked else 0,
    }
    if len(_abuse_hits) > 10000:
        _abuse_hits.clear()
    return blocked


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > MAX_REQUEST_SIZE:
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

import re
from urllib.parse import parse_qs, urlparse

import httpx


logger = get_logger("social.youtube")

_cache = TTLCache(ttl=CACHE_TTL)

_FORMAT_RE = re.compile(r"(\d{3,4})\s*[pP]")
_K_RE = re.compile(r"\b([248])\s*[kK]\b")
_EXT_RE = re.compile(r"\[\.([a-zA-Z0-9]+)\]")


def _mime_from_url(url):
    try:
        query = parse_qs(urlparse(url).query)
        values = query.get("mime") or []
        if values:
            return values[0].split(";")[0].strip().lower()
    except Exception:
        pass
    return ""


def _itag_from_url(url):
    try:
        query = parse_qs(urlparse(url).query)
        values = query.get("itag") or []
        if values:
            return values[0]
    except Exception:
        pass
    return ""


def _quality_from_format(format_text):
    if not format_text or not isinstance(format_text, str):
        return ""
    match = _FORMAT_RE.search(format_text)
    if match:
        return "%sp" % match.group(1)
    match = _K_RE.search(format_text)
    if match:
        return K_LABELS.get(match.group(1), "")
    return ""


def _ext_from_format(format_text, mime):
    if format_text and isinstance(format_text, str):
        match = _EXT_RE.search(format_text)
        if match:
            return match.group(1).lower()
    if "/" in mime:
        subtype = mime.split("/", 1)[1].split(";")[0].strip().lower()
        if subtype == "mp4":
            return "mp4"
        if subtype in ("webm", "weba"):
            return subtype
        if subtype in ("x-m4a", "m4a"):
            return "m4a"
        if subtype == "aac":
            return "aac"
    return ""


def _classify(mime, ext):
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if ext in AUDIO_EXTENSIONS and ext not in VIDEO_EXTENSIONS:
        return "audio"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return ""


def _parse_media_entry(entry):
    if not isinstance(entry, dict):
        return None
    url = entry.get("url")
    if not url or not isinstance(url, str) or not url.startswith("https://"):
        return None
    format_text = entry.get("format")
    mime = _mime_from_url(url)
    ext = _ext_from_format(format_text, mime)
    kind = _classify(mime, ext)
    if not kind:
        return None
    quality = _quality_from_format(format_text)
    if kind == "audio" and not quality:
        quality = ext.upper() if ext else "AUDIO"
    if kind == "video" and not quality:
        return None
    size_bytes = entry.get("fileSize")
    try:
        size_bytes = int(size_bytes) if size_bytes is not None else None
    except (TypeError, ValueError):
        size_bytes = None
    if size_bytes is None and isinstance(format_text, str):
        size_bytes = parse_size_text(format_text)
    return {
        "url": url,
        "kind": kind,
        "quality": quality,
        "ext": ext or ("mp4" if kind == "video" else "m4a"),
        "mime": mime,
        "size_bytes": size_bytes,
        "itag": _itag_from_url(url),
    }


async def _call_upstream(video_id):
    payload = {"url": "https://www.youtube.com/watch?v=%s" % video_id}
    headers = {
        "Origin": "https://www.ytultra.com",
        "Referer": "https://www.ytultra.com/",
        "User-Agent": BROWSER_USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    timeout = httpx.Timeout(UPSTREAM_TIMEOUT, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(YTDL_API_URL, json=payload, headers=headers)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
        logger.warning("upstream request failed: %s", type(exc).__name__)
        raise APIError()
    if response.status_code != 200:
        logger.warning("upstream status %s", response.status_code)
        raise APIError()
    try:
        body = response.json()
    except ValueError:
        raise APIError()
    if not isinstance(body, dict):
        raise APIError()
    data = body.get("data")
    if not isinstance(data, dict):
        raise APIError()
    return data


def _dedupe(items):
    seen = set()
    unique = []
    for item in items:
        key = item.get("itag") or item.get("url")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _sort_videos(items):
    return sorted(items, key=lambda m: quality_rank(m["quality"]), reverse=True)


def _sort_audios(items):
    def key(item):
        ext = item["ext"]
        pref = 0 if ext == "m4a" else (1 if ext == "aac" else 2)
        size = item.get("size_bytes") or 0
        return (pref, -size)
    return sorted(items, key=key)


async def fetch_media(page_url):
    video_id = validate_youtube_url(page_url)
    cached = _cache.get(video_id)
    if cached is not None:
        return cached
    data = await _call_upstream(video_id)
    raw_medias = data.get("medias")
    if not isinstance(raw_medias, list) or not raw_medias:
        raise MediaNotFound()
    parsed = []
    for entry in raw_medias:
        item = _parse_media_entry(entry)
        if item:
            parsed.append(item)
    parsed = _dedupe(parsed)
    videos = _sort_videos([m for m in parsed if m["kind"] == "video"])
    audios = _sort_audios([m for m in parsed if m["kind"] == "audio"])
    if not videos and not audios:
        raise MediaNotFound()
    title = data.get("title")
    if not title or not isinstance(title, str):
        title = "YouTube Video"
    title = title.strip()[:200] or "YouTube Video"
    duration = data.get("duration")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    thumbnail = validate_thumbnail_url(data.get("imageUrl"))
    result = {
        "video_id": video_id,
        "title": title,
        "duration": duration,
        "thumbnail": thumbnail,
        "videos": videos,
        "audios": audios,
    }
    _cache.set(video_id, result)
    return result

from urllib.parse import urlparse

PLATFORM_HOSTS = {
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "youtu.be": "youtube",
    "music.youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "m.tiktok.com": "tiktok",
    "vm.tiktok.com": "tiktok",
    "vt.tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "fb.watch": "facebook",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    "mobile.twitter.com": "twitter",
}

PLATFORM_NAMES = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "X (Twitter)",
    "unknown": "Video",
}

COBALT_PLATFORMS = {"tiktok", "instagram", "twitter"}


def detect_platform(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "unknown"
    if not host:
        return "unknown"
    if host in PLATFORM_HOSTS:
        return PLATFORM_HOSTS[host]
    for suffix in ("tiktok.com", "instagram.com", "facebook.com", "twitter.com", "x.com"):
        if host.endswith("." + suffix):
            return PLATFORM_HOSTS.get(suffix, "unknown")
    return "unknown"


def platform_display_name(platform):
    return PLATFORM_NAMES.get(platform, "Video")


def uses_cobalt(platform):
    return platform in COBALT_PLATFORMS

import asyncio
import time
from urllib.parse import urlparse

import httpx


logger = get_logger("social.cobalt")

DIRECTORY_URL = "https://cobalt.directory/api/working?type=api"

FALLBACK_INSTANCES = [
    "https://cobaltapi.cjs.nz",
    "https://api.qwkuns.me",
    "https://cobaltapi.squair.xyz",
    "https://api.dl.woof.monster",
    "https://api.cobalt.liubquanti.click",
    "https://api.kektube.com",
]

_instances_cache = {"at": 0.0, "urls": []}
INSTANCES_TTL = 3600.0


def _instance_host(instance_url):
    try:
        return (urlparse(instance_url).hostname or "").lower()
    except ValueError:
        return ""


def get_instances():
    now = time.monotonic()
    if _instances_cache["urls"] and now - _instances_cache["at"] < INSTANCES_TTL:
        return _instances_cache["urls"]
    urls = []
    if COBALT_API_URL:
        urls = [COBALT_API_URL.rstrip("/")]
    else:
        try:
            resp = httpx.get(DIRECTORY_URL, timeout=10.0, headers={"User-Agent": BROWSER_USER_AGENT})
            data = resp.json()
            seen = set()
            for group in (data.get("data") or {}).values():
                for inst in group or []:
                    if isinstance(inst, str) and inst.startswith("https://") and inst not in seen:
                        seen.add(inst)
                        urls.append(inst.rstrip("/"))
        except Exception as exc:
            logger.warning("cobalt directory failed: %s", type(exc).__name__)
        if not urls:
            urls = list(FALLBACK_INSTANCES)
    _instances_cache["at"] = now
    _instances_cache["urls"] = urls
    return urls


def _post_instance(instance, payload):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
    }
    timeout = httpx.Timeout(COBALT_TIMEOUT, connect=10.0)
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.post(instance, json=payload)
    if resp.status_code != 200:
        raise ConversionError()
    try:
        return resp.json()
    except ValueError:
        raise ConversionError()


def _pick_result(body):
    status = body.get("status", "error")
    if status in ("tunnel", "redirect"):
        url = body.get("url", "")
        if not url:
            raise MediaNotFound()
        return [{
            "url": url,
            "filename": body.get("filename", "media"),
            "kind": "file",
        }]
    if status == "picker":
        items = []
        for entry in body.get("picker") or []:
            url = entry.get("url", "")
            if not url:
                continue
            items.append({
                "url": url,
                "filename": "media_%d" % (len(items) + 1),
                "kind": "photo" if entry.get("type") == "photo" else "file",
            })
        audio_url = body.get("audio") or ""
        if audio_url:
            items.append({
                "url": audio_url,
                "filename": body.get("audioFilename", "audio"),
                "kind": "audio",
            })
        if not items:
            raise MediaNotFound()
        return items
    raise MediaNotFound()


def _call_cobalt(payload):
    last_error = None
    for instance in get_instances():
        try:
            body = _post_instance(instance, payload)
        except Exception as exc:
            last_error = exc
            logger.warning("cobalt instance failed %s: %s", _instance_host(instance), type(exc).__name__)
            continue
        if not isinstance(body, dict):
            continue
        if body.get("status") == "error":
            code = ""
            try:
                code = body.get("error", {}).get("code", "")
            except AttributeError:
                pass
            logger.warning("cobalt error %s: %s", _instance_host(instance), code)
            last_error = MediaNotFound()
            continue
        try:
            items = _pick_result(body)
        except (MediaNotFound, ConversionError) as exc:
            last_error = exc
            continue
        for item in items:
            item["instance_host"] = _instance_host(instance)
        return items
    if isinstance(last_error, Exception):
        raise last_error
    raise MediaNotFound()


COBALT_QUALITIES = ["360", "720", "1080"]


async def _fetch_quality_async(url, quality):
    payload = {"url": url, "videoQuality": quality}
    try:
        items = await asyncio.to_thread(_call_cobalt, payload)
        videos = [i for i in items if i["kind"] != "audio"]
        result = videos or items
        if result:
            result[0]["quality_label"] = "%sp" % quality
            return result[0]
    except Exception as exc:
        logger.warning("cobalt quality %s failed: %s", quality, type(exc).__name__)
    return None


def fetch_video(url):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _fetch_all_qualities(url)).result()
    return asyncio.run(_fetch_all_qualities(url))


async def _fetch_all_qualities(url):
    results = await asyncio.gather(*[_fetch_quality_async(url, q) for q in COBALT_QUALITIES])
    seen_urls = set()
    items = []
    for item in results:
        if not item:
            continue
        u = item.get("url", "")
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        items.append(item)
    if not items:
        payload = {"url": url, "videoQuality": "1080"}
        items = _call_cobalt(payload)
        videos = [i for i in items if i["kind"] != "audio"]
        result = videos or items
        if result:
            result[0]["quality_label"] = "HD"
        return result
    items.sort(key=lambda x: int(x.get("quality_label", "0p")[:-1] or 0))
    return items


def fetch_audio_mp3(url):
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "192",
    }
    return _call_cobalt(payload)

import asyncio
import re

import httpx


API_URL = "https://fdown.isuru.eu.org/download"
TIMEOUT = 60.0

QUALITY_MAP = {
    "2560p": "best",
    "1920p": "1080p",
    "1280p": "1080p",
    "960p": "720p",
}


def _api_quality(quality):
    q = str(quality or "").strip().lower()
    if q in ("best", "worst", "360p", "720p", "1080p"):
        return q
    return QUALITY_MAP.get(q, "best")


def _post(url, quality):
    resp = httpx.post(
        API_URL,
        json={"url": url, "quality": quality},
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://fdown.isuru.eu.org",
            "Referer": "https://fdown.isuru.eu.org/",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise MediaNotFound()
    return data


async def _apost(url, quality):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            API_URL,
            json={"url": url, "quality": quality},
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Origin": "https://fdown.isuru.eu.org",
                "Referer": "https://fdown.isuru.eu.org/",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise MediaNotFound()
        return data


def _quality_number(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else 0


def _head_size(url):
    try:
        resp = httpx.head(
            url,
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        if resp.status_code == 200:
            length = resp.headers.get("content-length", "")
            if length.isdigit() and int(length) > 0:
                return int(length)
    except Exception:
        pass
    return None


def _clean_formats(data):
    formats = data.get("available_formats", [])
    if not isinstance(formats, list):
        return []
    seen = {}
    for item in formats:
        if not isinstance(item, dict):
            continue
        quality = str(item.get("quality", "")).strip()
        url = str(item.get("url", "")).strip()
        if not quality or not url:
            continue
        if quality not in seen:
            seen[quality] = {
                "quality": quality,
                "url": url,
                "ext": str(item.get("ext", "mp4")).strip() or "mp4",
            }
    ordered = sorted(seen.values(), key=lambda x: _quality_number(x["quality"]), reverse=True)
    return ordered


async def _fetch_muxed_url(url, api_quality):
    try:
        data = await _apost(url, api_quality)
        direct = str(data.get("download_url", "")).strip()
        if direct:
            return direct
    except Exception:
        pass
    return ""


async def fetch_facebook_video_async(url):
    data = _post(url, "best")
    formats = _clean_formats(data)
    if not formats:
        direct = str(data.get("download_url", "")).strip()
        if not direct:
            raise MediaNotFound()
        formats = [{"quality": "HD", "url": direct, "ext": "mp4"}]
    info = data.get("video_info", {}) if isinstance(data.get("video_info"), dict) else {}
    title = str(info.get("title", "")).strip()
    needed = sorted({_api_quality(f["quality"]) for f in formats})
    muxed = {}
    results = await asyncio.gather(*[_fetch_muxed_url(url, q) for q in needed])
    for q, direct in zip(needed, results):
        if direct:
            muxed[q] = direct
    best_fallback = str(data.get("download_url", "")).strip()
    items = []
    for fmt in formats:
        api_q = _api_quality(fmt["quality"])
        direct_url = muxed.get(api_q) or best_fallback or fmt["url"]
        items.append({
            "url": direct_url,
            "quality": fmt["quality"],
            "filesize": _head_size(direct_url),
            "filename": "%s_%s.%s" % (title[:40] or "facebook_video", fmt["quality"], fmt["ext"]),
            "instance_host": "",
            "title": title,
            "thumbnail": str(info.get("thumbnail", "")),
            "duration": info.get("duration"),
        })
    return items


def fetch_facebook_video(url):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, fetch_facebook_video_async(url)).result()
    return asyncio.run(fetch_facebook_video_async(url))


def fetch_direct_url(original_url, quality):
    data = _post(original_url, _api_quality(quality))
    direct = str(data.get("download_url", "")).strip()
    if not direct:
        formats = _clean_formats(data)
        if formats:
            direct = formats[0]["url"]
    if not direct:
        raise MediaNotFound()
    return direct


def fetch_facebook_audio(url):
    return []


logger = get_logger("handler.youtube")


def _media_token(item, title, audio_url=""):
    payload = {
        "u": item["url"],
        "t": title,
        "e": item["ext"],
        "m": item["mime"],
        "k": item["kind"],
        "q": item["quality"],
        "p": "youtube",
    }
    if audio_url and item["kind"] == "video":
        payload["a"] = audio_url
    return issue_token(payload)


def _quality_num(q):
    import re
    m = re.search(r"(\d+)", str(q or ""))
    return int(m.group(1)) if m else 0


def _card(item, title, audio_url=""):
    return {
        "token": _media_token(item, title, audio_url),
        "type": item["kind"],
        "quality": item["quality"],
        "format": item["ext"].upper(),
        "size": format_size(item.get("size_bytes")),
        "size_bytes": item.get("size_bytes"),
    }


async def analyze(body):
    data = validate_json_body(body)
    raw_url = data.get("url", "")
    if not isinstance(raw_url, str):
        raise InvalidURL()
    validate_youtube_url(raw_url.strip())
    result = await fetch_media(raw_url.strip())
    title = result["title"]
    audios = result["audios"]
    best_audio_url = audios[0]["url"] if audios else ""
    videos_sorted = sorted(result["videos"], key=lambda v: _quality_num(v["quality"]))
    audios_sorted = sorted(audios, key=lambda a: _quality_num(a["quality"]))
    media = [_card(v, title, best_audio_url) for v in videos_sorted]
    media += [_card(a, title) for a in audios_sorted]
    return {
        "success": True,
        "title": title,
        "duration": result["duration"],
        "thumbnail": result["thumbnail"],
        "mp3_available": mp3_available(),
        "media": media,
    }


logger = get_logger("handler.fetch")


def _ext_from_filename(filename):
    name = (filename or "").rsplit(".", 1)
    if len(name) == 2 and 1 <= len(name[1]) <= 5 and name[1].isalnum():
        return name[1].lower()
    return "mp4"


def _mime_for_ext(ext):
    return {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "mov": "video/quicktime",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "opus": "audio/opus",
        "ogg": "audio/ogg",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }.get(ext, "application/octet-stream")


def _cobalt_token(item, title, kind, quality, original_url, platform=""):
    ext = _ext_from_filename(item.get("filename", ""))
    if kind == "audio":
        ext = "mp3"
    payload = {
        "u": item["url"],
        "t": title,
        "e": ext,
        "m": _mime_for_ext(ext),
        "k": kind,
        "q": quality,
        "h": item.get("instance_host", ""),
        "o": original_url,
    }
    if platform:
        payload["p"] = platform
    return issue_token(payload)


def _format_size(num_bytes):
    if not num_bytes or num_bytes <= 0:
        return "size unknown"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return "%d B" % int(size)
            return "%.1f %s" % (size, unit)
        size /= 1024
    return "size unknown"


def _cobalt_card(item, title, kind, quality, original_url, direct_mp3=False, platform=""):
    ext = _ext_from_filename(item.get("filename", ""))
    if kind == "audio":
        ext = "mp3"
    size_bytes = item.get("filesize")
    card = {
        "token": _cobalt_token(item, title, kind, quality, original_url, platform),
        "type": kind,
        "quality": quality,
        "format": ext.upper(),
        "size": _format_size(size_bytes),
        "size_bytes": size_bytes,
    }
    if direct_mp3:
        card["direct_mp3"] = True
    return card


def _clean_title(filename, platform):
    name = (filename or "").rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    if len(name) >= 4:
        return name[:120]
    return "%s Video" % platform_display_name(platform)


async def universal_analyze(body):
    data = validate_json_body(body)
    raw_url = data.get("url", "")
    if not isinstance(raw_url, str):
        raise InvalidURL()
    url = validate_media_url(raw_url)
    platform = detect_platform(url)
    if platform == "youtube":
        result = await analyze({"url": url})
        result["platform"] = "youtube"
        result["platform_name"] = platform_display_name("youtube")
        return result
    if platform == "facebook":
        title = "%s Video" % platform_display_name(platform)
        media = []
        try:
            videos = fetch_facebook_video(url)
        except Exception as exc:
            logger.warning("facebook video failed: %s", type(exc).__name__)
            videos = []
        if videos:
            first = videos[0]
            if first.get("title"):
                title = first["title"][:80]
            thumbnail = first.get("thumbnail", "")
            duration = first.get("duration")
        else:
            raise MediaNotFound()
        for item in videos:
            media.append(_cobalt_card(item, title, "video", item.get("quality") or "HD", url, platform="facebook"))
        return {
            "success": True,
            "platform": platform,
            "platform_name": platform_display_name(platform),
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "mp3_available": False,
            "media": media,
        }
    if not uses_cobalt(platform):
        raise UnsupportedPlatform()
    title = "%s Video" % platform_display_name(platform)
    media = []
    try:
        videos = fetch_video(url)
    except Exception as exc:
        logger.warning("cobalt video failed: %s", type(exc).__name__)
        videos = []
    mp3_items = []
    try:
        mp3_items = fetch_audio_mp3(url)
    except Exception as exc:
        logger.warning("cobalt audio failed: %s", type(exc).__name__)
    if videos:
        title = _clean_title(videos[0].get("filename", ""), platform)
    if not videos and not mp3_items:
        raise MediaNotFound()
    for idx, item in enumerate(videos):
        label = item.get("quality_label") or ("HD" if len(videos) == 1 else "Video %d" % (idx + 1))
        media.append(_cobalt_card(item, title, "video", label, url))
    for item in mp3_items:
        media.append(_cobalt_card(item, title, "audio", "MP3 192kbps", url, direct_mp3=True))
    return {
        "success": True,
        "platform": platform,
        "platform_name": platform_display_name(platform),
        "title": title,
        "duration": None,
        "thumbnail": "",
        "mp3_available": bool(mp3_items) or mp3_available(),
        "media": media,
    }

import httpx


logger = get_logger("handler.download")


def resolve_token(token):
    payload = verify_token(token)
    if payload is None:
        raise MediaExpired()
    url = payload.get("u", "")
    instance_host = payload.get("h", "")
    try:
        if instance_host:
            validate_cobalt_download_url(url, instance_host)
        else:
            validate_download_url(url)
    except ValidationError:
        raise MediaExpired()
    return payload


def media_info(token):
    payload = resolve_token(token)
    kind = payload.get("k", "")
    quality = payload.get("q", "")
    ext = payload.get("e", "")
    title = payload.get("t", "media")
    if kind == "video":
        filename = safe_filename("%s_%s" % (title, quality), ext)
    else:
        filename = safe_filename("%s_%s" % (title, ext.upper()), ext)
    return {
        "success": True,
        "filename": filename,
        "kind": kind,
        "quality": quality,
        "format": ext.upper(),
        "mime": payload.get("m", ""),
    }


def _tunnel_alive(url):
    try:
        resp = httpx.head(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        content_type = resp.headers.get("content-type", "").lower()
        return resp.status_code == 200 and "json" not in content_type
    except Exception:
        return False


def _fresh_cobalt_url(original_url):
    try:
        items = fetch_video(original_url)
    except Exception as exc:
        logger.warning("cobalt refresh failed: %s", type(exc).__name__)
        return ""
    if not items:
        return ""
    item = items[0]
    url = item.get("url", "")
    host = item.get("instance_host", "")
    if not url or not host:
        return ""
    try:
        validate_cobalt_download_url(url, host)
    except ValidationError:
        return ""
    return url


def download_target(token):
    payload = resolve_token(token)
    url = payload.get("u", "")
    if not url:
        raise MediaNotFound()
    if payload.get("p") == "facebook":
        original_url = payload.get("o", "")
        quality = payload.get("q", "")
        try:
            return fetch_direct_url(original_url, quality)
        except Exception as exc:
            logger.warning("facebook direct url failed: %s", type(exc).__name__)
            return url
    instance_host = payload.get("h", "")
    original_url = payload.get("o", "")
    if instance_host and original_url and not _tunnel_alive(url):
        fresh = _fresh_cobalt_url(original_url)
        if fresh:
            return fresh
    return url


def is_facebook_download(token):
    payload = verify_token(token)
    return bool(payload and payload.get("p") == "facebook")


def is_youtube_download(token):
    payload = verify_token(token)
    return bool(payload and payload.get("p") == "youtube" and payload.get("k") == "video")


def youtube_download_info(token):
    payload = resolve_token(token)
    url = payload.get("u", "")
    if not url:
        raise MediaNotFound()
    try:
        validate_download_url(url)
    except ValidationError:
        raise MediaExpired()
    audio_url = payload.get("a", "")
    if audio_url:
        try:
            validate_download_url(audio_url)
        except ValidationError:
            audio_url = ""
    title = payload.get("t", "youtube_video")
    quality = payload.get("q", "")
    ext = payload.get("e", "mp4")
    filename = safe_filename("%s_%s" % (title, quality or "HD"), ext)
    return {
        "url": url,
        "audio_url": audio_url,
        "filename": filename,
        "mime": payload.get("m", "video/mp4"),
    }


def facebook_download_info(token):
    payload = resolve_token(token)
    url = payload.get("u", "")
    if not url:
        raise MediaNotFound()
    try:
        validate_download_url(url)
    except ValidationError:
        raise MediaExpired()
    title = payload.get("t", "facebook_video")
    quality = payload.get("q", "")
    ext = payload.get("e", "mp4")
    filename = safe_filename("%s_%s" % (title, quality or "HD"), ext)
    return {"url": url, "filename": filename, "mime": payload.get("m", "video/mp4")}



def pick_best_audio(audios):
    if not audios:
        raise MediaNotFound()
    def key(item):
        ext = item.get("ext", "")
        pref = 0 if ext == "m4a" else (1 if ext == "aac" else 2)
        return (pref, -(item.get("size_bytes") or 0))
    return sorted(audios, key=key)[0]


def normalize_card(item, title):
    return {
        "type": item["kind"],
        "quality": item["quality"],
        "format": item["ext"].upper(),
        "size": format_size(item.get("size_bytes")),
        "size_bytes": item.get("size_bytes"),
    }


def split_media(videos, audios):
    return list(videos), list(audios)

import asyncio

import httpx


logger = get_logger("handler.mp3")


async def _feed_source(url, stdin):
    validate_download_url(url)
    timeout = httpx.Timeout(DOWNLOAD_TIMEOUT, connect=10.0)
    total = 0
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": BROWSER_USER_AGENT}) as response:
                if response.status_code != 200:
                    raise ConversionError()
                async for chunk in response.aiter_bytes(65536):
                    total += len(chunk)
                    if total > MP3_MAX_SOURCE_BYTES:
                        raise ConversionError()
                    stdin.write(chunk)
                    await stdin.drain()
    except (httpx.TimeoutException, httpx.HTTPError, OSError, ConnectionError) as exc:
        logger.warning("source feed failed: %s", type(exc).__name__)
        raise ConversionError()
    finally:
        try:
            stdin.close()
        except Exception:
            pass
    if total == 0:
        raise ConversionError()


async def _spawn_ffmpeg(title):
    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        raise ConversionUnavailable()
    args = [
        ffmpeg, "-y",
        "-i", "pipe:0",
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", MP3_BITRATE,
        "-metadata", "title=%s" % title[:120],
        "-f", "mp3",
        "pipe:1",
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("ffmpeg spawn failed: %s", type(exc).__name__)
        raise ConversionError()
    return process


async def mp3_stream(token):
    if not isinstance(token, str):
        raise MediaExpired()
    payload = resolve_token(token)
    if payload.get("k") != "audio":
        raise ValidationError()
    url = payload.get("u", "")
    title = payload.get("t", "audio")
    if not local_converter_available():
        raise ConversionUnavailable()
    process = await _spawn_ffmpeg(title)
    feed_task = asyncio.ensure_future(_feed_source(url, process.stdin))
    filename = safe_filename("%s_192kbps" % title, "mp3")
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(process.stdout.read(65536), timeout=FFMPEG_TIMEOUT)
            except asyncio.TimeoutError:
                raise ConversionError()
            if not chunk:
                break
            yield chunk
    finally:
        if not feed_task.done():
            feed_task.cancel()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        if process.returncode not in (0, None):
            logger.warning("ffmpeg exited %s", process.returncode)
    if feed_task.done() and feed_task.exception() is not None:
        raise feed_task.exception()


def mp3_handler_available():
    return mp3_available()

import os
import sys


from fastapi import Request
from fastapi.responses import JSONResponse


logger = get_logger("api.youtube")


async def youtube_endpoint(request: Request):
    check_general_limit(request)
    try:
        body = await request.json()
    except Exception:
        raise AppError()
    if not isinstance(body, dict):
        raise ValidationError()
    result = await analyze(body)
    return JSONResponse(result)

import asyncio
import os
import sys


import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse


logger = get_logger("api.download")


async def download_endpoint(request: Request):
    check_general_limit(request)
    token = request.query_params.get("token", "")
    if not token or len(token) > 4096:
        raise ValidationError()
    if is_facebook_download(token):
        info = facebook_download_info(token)
        return _proxy_download(info["url"], info["filename"], info["mime"])
    if is_youtube_download(token):
        info = youtube_download_info(token)
        if info["audio_url"]:
            return await _mux_download(info)
        return _proxy_download(info["url"], info["filename"], info["mime"])
    target = download_target(token)
    return RedirectResponse(url=target, status_code=302)


def _proxy_download(url, filename, mime):
    def _stream():
        try:
            with httpx.stream(
                "GET",
                url,
                timeout=120.0,
                follow_redirects=True,
                headers={"User-Agent": BROWSER_USER_AGENT},
            ) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_bytes(chunk_size=65536):
                    if chunk:
                        yield chunk
        except Exception as exc:
            logger.warning("proxy failed: %s", type(exc).__name__)
            return

    safe_name = filename.replace('"', "").strip() or "video.mp4"
    headers = {"Content-Disposition": 'attachment; filename="%s"' % safe_name}
    return StreamingResponse(
        _stream(),
        media_type=mime or "video/mp4",
        headers=headers,
    )


async def _mux_download(info):
    ffmpeg = config.resolve_ffmpeg()
    if not ffmpeg:
        return _proxy_download(info["url"], info["filename"], info["mime"])
    args = [
        ffmpeg, "-y",
        "-headers", "User-Agent: %s\r\n" % BROWSER_USER_AGENT,
        "-i", info["url"],
        "-headers", "User-Agent: %s\r\n" % BROWSER_USER_AGENT,
        "-i", info["audio_url"],
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "mp4",
        "-movflags", "frag_keyframe+empty_moov",
        "pipe:1",
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("ffmpeg spawn failed: %s", type(exc).__name__)
        return _proxy_download(info["url"], info["filename"], info["mime"])

    async def _stream():
        try:
            while True:
                chunk = await process.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                process.kill()
            except Exception:
                pass
            await process.wait()

    safe_name = info["filename"].replace('"', "").strip() or "video.mp4"
    headers = {"Content-Disposition": 'attachment; filename="%s"' % safe_name}
    return StreamingResponse(_stream(), media_type="video/mp4", headers=headers)


async def download_head_endpoint(request: Request):
    check_general_limit(request)
    token = request.query_params.get("token", "")
    if not token or len(token) > 4096:
        raise ValidationError()
    resolve_token(token)
    return JSONResponse(status_code=200, content={"ok": True})

import os
import sys


from fastapi import Request
from fastapi.responses import JSONResponse



async def media_endpoint(request: Request):
    check_general_limit(request)
    token = request.query_params.get("token", "")
    if not token or len(token) > 4096:
        raise ValidationError()
    return JSONResponse(media_info(token))

import os
import sys


from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse


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
    if not mp3_handler_available():
        raise ConversionUnavailable()
    payload = resolve_token(token)
    title = payload.get("t", "audio")
    filename = safe_filename("%s_192kbps" % title, "mp3")
    headers = {
        "Content-Disposition": 'attachment; filename="%s"' % filename.replace('"', ""),
    }
    return StreamingResponse(
        mp3_stream(token),
        media_type="audio/mpeg",
        headers=headers,
    )

import os
import sys


from fastapi.responses import JSONResponse


async def health_endpoint():
    return JSONResponse({"status": "ok"})

import os
import sys


from fastapi import Request
from fastapi.responses import JSONResponse


logger = get_logger("api.fetch")


async def fetch_endpoint(request: Request):
    check_general_limit(request)
    try:
        body = await request.json()
    except Exception:
        raise ValidationError()
    result = await universal_analyze(body)
    return JSONResponse(result)

app = FastAPI(title="RIKA MEDIA DOWNLOADER", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SecurityMiddleware)
app.post("/api/youtube")(youtube_endpoint)
app.get("/api/download")(download_endpoint)
app.head("/api/download")(download_head_endpoint)
app.get("/api/media")(media_endpoint)
app.post("/api/mp3")(mp3_endpoint)
app.get("/api/health")(health_endpoint)
app.post("/api/fetch")(fetch_endpoint)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        {"success": False, "error": exc.safe_message},
        status_code=exc.status_code,
    )

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(
        {"success": False, "error": GENERIC_ERROR},
        status_code=500,
    )
