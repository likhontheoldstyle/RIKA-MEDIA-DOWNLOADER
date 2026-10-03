import httpx

from core import utils
from core.constants import BROWSER_USER_AGENT
from core.exceptions import MediaExpired, MediaNotFound, ValidationError
from core.logger import get_logger
from security.validation import validate_cobalt_download_url, validate_download_url
from social.cobalt import fetch_video
from social.facebook import fetch_direct_url

logger = get_logger("handler.download")


def resolve_token(token):
    payload = utils.verify_token(token)
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
        filename = utils.safe_filename("%s_%s" % (title, quality), ext)
    else:
        filename = utils.safe_filename("%s_%s" % (title, ext.upper()), ext)
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
    payload = utils.verify_token(token)
    return bool(payload and payload.get("p") == "facebook")


def is_youtube_download(token):
    payload = utils.verify_token(token)
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
    filename = utils.safe_filename("%s_%s" % (title, quality or "HD"), ext)
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
    filename = utils.safe_filename("%s_%s" % (title, quality or "HD"), ext)
    return {"url": url, "filename": filename, "mime": payload.get("m", "video/mp4")}
