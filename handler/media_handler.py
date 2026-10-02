from core import utils
from core.exceptions import MediaNotFound


def pick_best_audio(audios):
    if not audios:
        raise MediaNotFound()
    def key(item):
        ext = item.get("ext", "")
        pref = 0 if ext == "m4a" else (1 if ext == "aac" else 2)
        return (pref, -(item.get("size_bytes") or 0))
    return sorted(audios, key=key)[0]


def normalize_card(item, title):
    return {
        "type": item["kind"],
        "quality": item["quality"],
        "format": item["ext"].upper(),
        "size": utils.format_size(item.get("size_bytes")),
        "size_bytes": item.get("size_bytes"),
    }


def split_media(videos, audios):
    return list(videos), list(audios)
