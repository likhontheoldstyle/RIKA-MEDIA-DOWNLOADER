from core import config, utils
from core.logger import get_logger
from security.validation import validate_json_body, validate_youtube_url
from social import youtube as yt

logger = get_logger("handler.youtube")


def _media_token(item, title):
    return utils.issue_token({
        "u": item["url"],
        "t": title,
        "e": item["ext"],
        "m": item["mime"],
        "k": item["kind"],
        "q": item["quality"],
    })


def _card(item, title):
    return {
        "token": _media_token(item, title),
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
    result = await yt.fetch_media(raw_url.strip())
    title = result["title"]
    media = [_card(v, title) for v in result["videos"]]
    media += [_card(a, title) for a in result["audios"]]
    return {
        "success": True,
        "title": title,
        "duration": result["duration"],
        "thumbnail": result["thumbnail"],
        "mp3_available": config.mp3_available(),
        "media": media,
    }
