import asyncio
import time
from urllib.parse import urlparse

import httpx

from core import config
from core.constants import BROWSER_USER_AGENT, COBALT_TIMEOUT
from core.exceptions import ConversionError, MediaNotFound
from core.logger import get_logger

logger = get_logger("social.cobalt")

DIRECTORY_URL = "https://cobalt.directory/api/working?type=api"

FALLBACK_INSTANCES = [
    "https://cobaltapi.cjs.nz",
    "https://api.qwkuns.me",
    "https://cobaltapi.squair.xyz",
    "https://api.dl.woof.monster",
    "https://api.cobalt.liubquanti.click",
    "https://api.kektube.com",
]

_instances_cache = {"at": 0.0, "urls": []}
INSTANCES_TTL = 3600.0


def _instance_host(instance_url):
    try:
        return (urlparse(instance_url).hostname or "").lower()
    except ValueError:
        return ""


def get_instances():
    now = time.monotonic()
    if _instances_cache["urls"] and now - _instances_cache["at"] < INSTANCES_TTL:
        return _instances_cache["urls"]
    urls = []
    if config.COBALT_API_URL:
        urls = [config.COBALT_API_URL.rstrip("/")]
    else:
        try:
            resp = httpx.get(DIRECTORY_URL, timeout=10.0, headers={"User-Agent": BROWSER_USER_AGENT})
            data = resp.json()
            seen = set()
            for group in (data.get("data") or {}).values():
                for inst in group or []:
                    if isinstance(inst, str) and inst.startswith("https://") and inst not in seen:
                        seen.add(inst)
                        urls.append(inst.rstrip("/"))
        except Exception as exc:
            logger.warning("cobalt directory failed: %s", type(exc).__name__)
        if not urls:
            urls = list(FALLBACK_INSTANCES)
    _instances_cache["at"] = now
    _instances_cache["urls"] = urls
    return urls


def _post_instance(instance, payload):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
    }
    timeout = httpx.Timeout(COBALT_TIMEOUT, connect=10.0)
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.post(instance, json=payload)
    if resp.status_code != 200:
        raise ConversionError()
    try:
        return resp.json()
    except ValueError:
        raise ConversionError()


def _pick_result(body):
    status = body.get("status", "error")
    if status in ("tunnel", "redirect"):
        url = body.get("url", "")
        if not url:
            raise MediaNotFound()
        return [{
            "url": url,
            "filename": body.get("filename", "media"),
            "kind": "file",
        }]
    if status == "picker":
        items = []
        for entry in body.get("picker") or []:
            url = entry.get("url", "")
            if not url:
                continue
            items.append({
                "url": url,
                "filename": "media_%d" % (len(items) + 1),
                "kind": "photo" if entry.get("type") == "photo" else "file",
            })
        audio_url = body.get("audio") or ""
        if audio_url:
            items.append({
                "url": audio_url,
                "filename": body.get("audioFilename", "audio"),
                "kind": "audio",
            })
        if not items:
            raise MediaNotFound()
        return items
    raise MediaNotFound()


def _call_cobalt(payload):
    last_error = None
    for instance in get_instances():
        try:
            body = _post_instance(instance, payload)
        except Exception as exc:
            last_error = exc
            logger.warning("cobalt instance failed %s: %s", _instance_host(instance), type(exc).__name__)
            continue
        if not isinstance(body, dict):
            continue
        if body.get("status") == "error":
            code = ""
            try:
                code = body.get("error", {}).get("code", "")
            except AttributeError:
                pass
            logger.warning("cobalt error %s: %s", _instance_host(instance), code)
            last_error = MediaNotFound()
            continue
        try:
            items = _pick_result(body)
        except (MediaNotFound, ConversionError) as exc:
            last_error = exc
            continue
        for item in items:
            item["instance_host"] = _instance_host(instance)
        return items
    if isinstance(last_error, Exception):
        raise last_error
    raise MediaNotFound()


COBALT_QUALITIES = ["360", "720", "1080"]


async def _fetch_quality_async(url, quality):
    payload = {"url": url, "videoQuality": quality}
    try:
        items = await asyncio.to_thread(_call_cobalt, payload)
        videos = [i for i in items if i["kind"] != "audio"]
        result = videos or items
        if result:
            result[0]["quality_label"] = "%sp" % quality
            return result[0]
    except Exception as exc:
        logger.warning("cobalt quality %s failed: %s", quality, type(exc).__name__)
    return None


def fetch_video(url):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _fetch_all_qualities(url)).result()
    return asyncio.run(_fetch_all_qualities(url))


async def _fetch_all_qualities(url):
    results = await asyncio.gather(*[_fetch_quality_async(url, q) for q in COBALT_QUALITIES])
    seen_urls = set()
    items = []
    for item in results:
        if not item:
            continue
        u = item.get("url", "")
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        items.append(item)
    if not items:
        payload = {"url": url, "videoQuality": "1080"}
        items = _call_cobalt(payload)
        videos = [i for i in items if i["kind"] != "audio"]
        result = videos or items
        if result:
            result[0]["quality_label"] = "HD"
        return result
    items.sort(key=lambda x: int(x.get("quality_label", "0p")[:-1] or 0))
    return items


def fetch_audio_mp3(url):
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "192",
    }
    return _call_cobalt(payload)
