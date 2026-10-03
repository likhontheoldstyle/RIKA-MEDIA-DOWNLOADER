from core import config, utils
from core.exceptions import InvalidURL, MediaNotFound, UnsupportedPlatform
from core.logger import get_logger
from security.validation import validate_json_body, validate_media_url
from social.cobalt import fetch_audio_mp3, fetch_video
from social.facebook import fetch_facebook_video
from social.platforms import detect_platform, platform_display_name, uses_cobalt
from handler.youtube_handler import analyze

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


def _cobalt_token(item, title, kind, quality, original_url):
    ext = _ext_from_filename(item.get("filename", ""))
    if kind == "audio":
        ext = "mp3"
    return utils.issue_token({
        "u": item["url"],
        "t": title,
        "e": ext,
        "m": _mime_for_ext(ext),
        "k": kind,
        "q": quality,
        "h": item.get("instance_host", ""),
        "o": original_url,
    })


def _cobalt_card(item, title, kind, quality, original_url, direct_mp3=False):
    ext = _ext_from_filename(item.get("filename", ""))
    if kind == "audio":
        ext = "mp3"
    card = {
        "token": _cobalt_token(item, title, kind, quality, original_url),
        "type": kind,
        "quality": quality,
        "format": ext.upper(),
        "size": "size unknown",
        "size_bytes": None,
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
            media.append(_cobalt_card(item, title, "video", item.get("quality") or "HD", url))
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
        label = "HD" if len(videos) == 1 else "Video %d" % (idx + 1)
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
        "mp3_available": bool(mp3_items) or config.mp3_available(),
        "media": media,
    }
