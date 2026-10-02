import ipaddress
import re
import socket
from urllib.parse import urlparse

from core import config
from core.constants import BLOCKED_HOSTS, BLOCKED_SCHEMES, DOWNLOAD_HOST_EXACT, DOWNLOAD_HOST_SUFFIXES, YOUTUBE_HOSTS
from core.exceptions import InvalidURL, UnsupportedPlatform, ValidationError


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
    if len(text) > config.MAX_URL_LENGTH:
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
    from core.constants import THUMBNAIL_HOST_SUFFIXES
    if not any(host.endswith(suffix) for suffix in THUMBNAIL_HOST_SUFFIXES):
        return ""
    return url


def validate_json_body(body, max_keys=10):
    if not isinstance(body, dict):
        raise ValidationError()
    if len(body) > max_keys:
        raise ValidationError()
    return body
