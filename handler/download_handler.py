from core import utils
from core.exceptions import MediaExpired, MediaNotFound, ValidationError
from security.validation import validate_download_url


def resolve_token(token):
    payload = utils.verify_token(token)
    if payload is None:
        raise MediaExpired()
    url = payload.get("u", "")
    try:
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


def download_target(token):
    payload = resolve_token(token)
    if not payload.get("u"):
        raise MediaNotFound()
    return payload["u"]
