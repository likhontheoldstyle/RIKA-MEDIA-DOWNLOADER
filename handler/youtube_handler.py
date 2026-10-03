from core import config, utils
from core.logger import get_logger
from security.validation import validate_json_body, validate_youtube_url
from social import youtube as yt

logger = get_logger("handler.youtube")


def _media_token(item, title, audio_url="", source_url=""):
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
    if source_url:
        payload["src"] = source_url
    return utils.issue_token(payload)


def _quality_num(q):
    import re
    m = re.search(r"(\d+)", str(q or ""))
    return int(m.group(1)) if m else 0


def _card(item, title, audio_url="", source_url=""):
    return {
        "token": _media_token(item, title, audio_url, source_url),
        "type": item["kind"],
        "quality": item["quality"],
        "format": item["ext"].upper(),
        "size": utils.format_size(item.get("size_bytes")),
        "size_bytes": item.get("size_bytes"),
    }


async def analyze(body):
    data = validate_json_body(body)
    raw_url = data.get("url", "")
    if not isinstance(raw_url, str):
        from core.exceptions import InvalidURL
        raise InvalidURL()
    validate_youtube_url(raw_url.strip())
    source_url = raw_url.strip()
    result = await yt.fetch_media(source_url)
    title = result["title"]
    audios = result["audios"]
    best_audio_url = audios[0]["url"] if audios else ""
    videos_sorted = sorted(result["videos"], key=lambda v: _quality_num(v["quality"]))
    audios_sorted = sorted(audios, key=lambda a: _quality_num(a["quality"]))
    media = [_card(v, title, best_audio_url, source_url) for v in videos_sorted]
    media += [_card(a, title, "", source_url) for a in audios_sorted]
    return {
        "success": True,
        "title": title,
        "duration": result["duration"],
        "thumbnail": result["thumbnail"],
        "mp3_available": config.mp3_available(),
        "media": media,
    }
