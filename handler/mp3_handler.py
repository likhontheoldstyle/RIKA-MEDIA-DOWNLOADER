import asyncio
import re

import httpx

from core import config, utils
from core.constants import BROWSER_USER_AGENT, DOWNLOAD_TIMEOUT, FFMPEG_TIMEOUT
from core.exceptions import ConversionError, ConversionUnavailable, MediaExpired, ValidationError
from core.logger import get_logger
from handler.download_handler import resolve_token
from security.validation import validate_download_url

logger = get_logger("handler.mp3")

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,}")
_FFMPEG_STARTUP_TIMEOUT = 25.0
_STDERR_MAX_BYTES = 8192


def _sanitize_stderr(text):
    cleaned = _URL_RE.sub("[url]", text)
    cleaned = _TOKEN_RE.sub("[token]", cleaned)
    return cleaned[:2000]


async def _refresh_youtube_audio_url(source_url):
    from social import youtube as yt
    from security.validation import validate_youtube_url
    try:
        validate_youtube_url(source_url)
    except Exception:
        return ""
    try:
        result = await yt.fetch_media(source_url)
        audios = result.get("audios", [])
        if audios:
            fresh_url = audios[0].get("url", "")
            if fresh_url:
                try:
                    validate_download_url(fresh_url)
                    return fresh_url
                except ValidationError:
                    pass
    except Exception as exc:
        logger.warning("youtube url refresh failed: %s", type(exc).__name__)
    return ""


async def _read_stderr(stream):
    try:
        data = await stream.read(_STDERR_MAX_BYTES)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


async def _feed_source(url, stdin):
    validate_download_url(url)
    timeout = httpx.Timeout(DOWNLOAD_TIMEOUT, connect=10.0)
    total = 0
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": BROWSER_USER_AGENT}) as response:
                if response.status_code != 200:
                    raise ConversionError()
                async for chunk in response.aiter_bytes(65536):
                    total += len(chunk)
                    if total > config.MP3_MAX_SOURCE_BYTES:
                        raise ConversionError()
                    stdin.write(chunk)
                    await stdin.drain()
    except (httpx.TimeoutException, httpx.HTTPError, OSError, ConnectionError) as exc:
        logger.warning("source feed failed: %s", type(exc).__name__)
        raise ConversionError()
    finally:
        try:
            stdin.close()
        except Exception:
            pass
    if total == 0:
        raise ConversionError()


async def _spawn_ffmpeg(title, url=""):
    ffmpeg = config.resolve_ffmpeg()
    if not ffmpeg:
        raise ConversionUnavailable()
    if url:
        args = [
            ffmpeg, "-y",
            "-headers", "User-Agent: %s\r\n" % BROWSER_USER_AGENT,
            "-i", url,
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", config.MP3_BITRATE,
            "-metadata", "title=%s" % title[:120],
            "-f", "mp3",
            "pipe:1",
        ]
        use_stdin = False
    else:
        args = [
            ffmpeg, "-y",
            "-i", "pipe:0",
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", config.MP3_BITRATE,
            "-metadata", "title=%s" % title[:120],
            "-f", "mp3",
            "pipe:1",
        ]
        use_stdin = True
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if use_stdin else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        logger.warning("ffmpeg spawn failed: %s", type(exc).__name__)
        raise ConversionError()
    return process, use_stdin


async def _cleanup(process, feed_task, stderr_text):
    if feed_task and not feed_task.done():
        feed_task.cancel()
    try:
        await asyncio.wait_for(process.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    if process.returncode not in (0, None):
        logger.warning("ffmpeg exited %s stderr=%s", process.returncode, _sanitize_stderr(stderr_text))
    if feed_task and feed_task.done() and feed_task.exception() is not None:
        raise feed_task.exception()


async def mp3_stream(token):
    if not isinstance(token, str):
        raise MediaExpired()
    payload = resolve_token(token)
    kind = payload.get("k", "")
    if kind not in ("audio", "video"):
        raise ValidationError()
    url = payload.get("u", "")
    if kind == "video":
        audio_url = payload.get("a", "")
        if audio_url:
            try:
                validate_download_url(audio_url)
                url = audio_url
            except ValidationError:
                pass
    platform = payload.get("p", "")
    if platform == "youtube":
        source_url = payload.get("src", "")
        if source_url:
            fresh_url = await _refresh_youtube_audio_url(source_url)
            if fresh_url:
                url = fresh_url
    if not url:
        raise ValidationError()
    validate_download_url(url)
    title = payload.get("t", "audio")
    if not config.local_converter_available():
        if config.remote_converter_available():
            logger.warning("remote converter configured but API contract unknown, local ffmpeg missing")
        raise ConversionUnavailable()
    process, use_stdin = await _spawn_ffmpeg(title, url)
    feed_task = None
    if use_stdin:
        feed_task = asyncio.ensure_future(_feed_source(url, process.stdin))
    stderr_task = asyncio.ensure_future(_read_stderr(process.stderr))
    filename = utils.safe_filename("%s_192kbps" % title, "mp3")
    stderr_text = ""
    try:
        try:
            first = await asyncio.wait_for(process.stdout.read(65536), timeout=_FFMPEG_STARTUP_TIMEOUT)
        except asyncio.TimeoutError:
            stderr_text = await stderr_task if stderr_task.done() else ""
            logger.warning("ffmpeg startup timeout stderr=%s", _sanitize_stderr(stderr_text))
            raise ConversionError()
        if not first:
            stderr_text = await stderr_task if stderr_task.done() else ""
            logger.warning("ffmpeg produced no output stderr=%s", _sanitize_stderr(stderr_text))
            raise ConversionError()
        yield first
        while True:
            try:
                chunk = await asyncio.wait_for(process.stdout.read(65536), timeout=FFMPEG_TIMEOUT)
            except asyncio.TimeoutError:
                raise ConversionError()
            if not chunk:
                break
            yield chunk
    finally:
        if not stderr_task.done():
            stderr_task.cancel()
        else:
            try:
                stderr_text = stderr_task.result()
            except Exception:
                pass
        await _cleanup(process, feed_task, stderr_text)


def mp3_handler_available():
    return config.mp3_available()
