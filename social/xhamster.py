import re
import json

import httpx

from core.constants import BROWSER_USER_AGENT
from core.exceptions import MediaNotFound

TIMEOUT = 30.0

VIDEO_URL_RE = re.compile(
    r"^https?://(?:www\.)?(?:xhamster\.com|xhamster\d*\.com)/videos/[^/]+$",
    re.IGNORECASE,
)

M3U8_RE = re.compile(
    r'<link rel="preload" href="(https://video-nss-[^"]+?\.m3u8[^"]*)"',
)

INITIALS_RE = re.compile(
    r"window\.initials=(\{.*?\});",
    re.DOTALL,
)

QUALITY_RE = re.compile(r"(\d+)x(\d+):(\d+p)")


def is_xhamster_url(url):
    return bool(VIDEO_URL_RE.match((url or "").strip()))


def _fetch_html(url):
    resp = httpx.get(
        url,
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    resp.raise_for_status()
    return resp.text


def _parse_initials(html):
    m = INITIALS_RE.search(html)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except (ValueError, TypeError):
        return {}


def _extract_m3u8(html):
    m = M3U8_RE.search(html)
    if not m:
        return "", []
    url = m.group(1)
    qualities = []
    for qm in QUALITY_RE.finditer(url):
        width, height, label = qm.groups()
        qualities.append({
            "quality": label,
            "width": int(width),
            "height": int(height),
        })
    qualities.sort(key=lambda x: x["height"])
    return url, qualities


def _m3u8_for_quality(master_url, quality_label):
    if "_TPL_" in master_url:
        return master_url.replace("_TPL_", quality_label)
    return master_url


def fetch_video_info(url):
    url = (url or "").strip()
    if not is_xhamster_url(url):
        raise MediaNotFound()
    try:
        html = _fetch_html(url)
    except Exception:
        raise MediaNotFound()
    data = _parse_initials(html)
    entity = data.get("videoEntity", {}) if isinstance(data.get("videoEntity"), dict) else {}
    title = str(entity.get("title", "")).strip() or "xHamster Video"
    duration = entity.get("duration")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    views = entity.get("views")
    thumbs = entity.get("thumbs", {}) if isinstance(entity.get("thumbs"), dict) else {}
    thumbnail = ""
    if isinstance(thumbs, dict):
        for key in ("thumbBig", "thumb", "poster"):
            val = thumbs.get(key)
            if isinstance(val, str) and val.startswith("http"):
                thumbnail = val
                break
            if isinstance(val, dict):
                for sub in val.values():
                    if isinstance(sub, str) and sub.startswith("http"):
                        thumbnail = sub
                        break
                if thumbnail:
                    break
    if not thumbnail:
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            thumbnail = m.group(1)
    master_url, qualities = _extract_m3u8(html)
    if not master_url:
        raise MediaNotFound()
    video_id = entity.get("id") or data.get("videoModel", {}).get("id", "")
    formats = []
    for q in qualities:
        formats.append({
            "quality": q["quality"],
            "width": q["width"],
            "height": q["height"],
            "url": _m3u8_for_quality(master_url, q["quality"]),
            "ext": "mp4",
        })
    if not formats:
        formats.append({
            "quality": "HD",
            "width": 0,
            "height": 0,
            "url": master_url.replace("_TPL_", "720p"),
            "ext": "mp4",
        })
    return {
        "video_id": str(video_id),
        "title": title[:200],
        "duration": duration,
        "views": views,
        "thumbnail": thumbnail,
        "formats": formats,
        "master_url": master_url,
    }


def fetch_search_results(query, page=1):
    search_url = "https://xhamster.com/search/%s" % httpx.QueryParams({"q": query}).get("q", query)
    if page > 1:
        search_url += "/%d" % page
    try:
        html = _fetch_html(search_url)
    except Exception:
        raise MediaNotFound()
    data = _parse_initials(html)
    results = []
    seen = set()
    for m in re.finditer(r'href="(https://xhamster\.com/videos/[^"]+)"', html):
        video_url = m.group(1)
        if video_url in seen:
            continue
        seen.add(video_url)
        results.append({"url": video_url})
        if len(results) >= 20:
            break
    return results
