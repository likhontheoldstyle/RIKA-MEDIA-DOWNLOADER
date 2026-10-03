import re

import httpx

from core.constants import BROWSER_USER_AGENT
from core.exceptions import MediaNotFound

API_URL = "https://fdown.isuru.eu.org/download"
TIMEOUT = 60.0


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


def _quality_number(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else 0


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


def fetch_facebook_video(url):
    data = _post(url, "best")
    formats = _clean_formats(data)
    if not formats:
        direct = str(data.get("download_url", "")).strip()
        if not direct:
            raise MediaNotFound()
        formats = [{"quality": "HD", "url": direct, "ext": "mp4"}]
    info = data.get("video_info", {}) if isinstance(data.get("video_info"), dict) else {}
    title = str(info.get("title", "")).strip()
    items = []
    for fmt in formats:
        items.append({
            "url": fmt["url"],
            "filename": "%s_%s.%s" % (title[:40] or "facebook_video", fmt["quality"], fmt["ext"]),
            "instance_host": "",
            "title": title,
            "thumbnail": str(info.get("thumbnail", "")),
            "duration": info.get("duration"),
        })
    return items


def fetch_facebook_audio(url):
    return []
