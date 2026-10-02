import re
from urllib.parse import parse_qs, urlparse

import httpx

from core import config, utils
from core.constants import (
    AUDIO_EXTENSIONS,
    BROWSER_USER_AGENT,
    K_LABELS,
    UPSTREAM_TIMEOUT,
    VIDEO_EXTENSIONS,
)
from core.exceptions import APIError, MediaNotFound
from core.logger import get_logger
from security.validation import validate_thumbnail_url, validate_youtube_url

logger = get_logger("social.youtube")

_cache = utils.TTLCache(ttl=config.CACHE_TTL)

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
        size_bytes = utils.parse_size_text(format_text)
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
            response = await client.post(config.YTDL_API_URL, json=payload, headers=headers)
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
    return sorted(items, key=lambda m: utils.quality_rank(m["quality"]), reverse=True)


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
