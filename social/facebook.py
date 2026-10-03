import asyncio
import re

import httpx

from core.constants import BROWSER_USER_AGENT
from core.exceptions import MediaNotFound

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
