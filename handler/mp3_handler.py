import asyncio
import json
import os
import tempfile

import httpx

from core import config, utils
from core.constants import DOWNLOAD_TIMEOUT, FFMPEG_TIMEOUT
from core.exceptions import ConversionError, ConversionUnavailable, MediaExpired, ValidationError
from core.logger import get_logger
from handler.download_handler import resolve_token
from security.validation import validate_download_url

logger = get_logger("handler.mp3")


async def _download_source(url, dest_path):
    validate_download_url(url)
    timeout = httpx.Timeout(DOWNLOAD_TIMEOUT, connect=10.0)
    total = 0
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                if response.status_code != 200:
                    raise ConversionError()
                with open(dest_path, "wb") as handle:
                    async for chunk in response.aiter_bytes(65536):
                        total += len(chunk)
                        if total > config.MP3_MAX_SOURCE_BYTES:
                            raise ConversionError()
                        handle.write(chunk)
    except (httpx.TimeoutException, httpx.HTTPError, OSError) as exc:
        logger.warning("source download failed: %s", type(exc).__name__)
        raise ConversionError()
    if total == 0:
        raise ConversionError()
    return dest_path


async def _run_ffmpeg(ffmpeg, src_path, out_path, title):
    args = [
        ffmpeg, "-y",
        "-i", src_path,
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", config.MP3_BITRATE,
        "-metadata", "title=%s" % title[:120],
        out_path,
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=FFMPEG_TIMEOUT)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            raise ConversionError()
        if process.returncode != 0:
            logger.warning("ffmpeg exited %s", process.returncode)
            raise ConversionError()
    except (OSError, ConversionError):
        raise ConversionError()
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise ConversionError()
    return out_path


async def _remote_convert(url, title):
    if not config.remote_converter_available():
        raise ConversionUnavailable()
    payload = {"audio_url": url, "format": "mp3", "bitrate": config.MP3_BITRATE, "title": title}
    headers = {"Content-Type": "application/json"}
    if config.CONVERTER_API_KEY:
        headers["X-API-Key"] = config.CONVERTER_API_KEY
    timeout = httpx.Timeout(FFMPEG_TIMEOUT, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(config.CONVERTER_URL, json=payload, headers=headers)
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        logger.warning("remote converter failed: %s", type(exc).__name__)
        raise ConversionError()
    if response.status_code != 200:
        raise ConversionError()
    try:
        body = response.json()
    except ValueError:
        raise ConversionError()
    download_url = body.get("download_url") if isinstance(body, dict) else None
    if not download_url:
        raise ConversionError()
    return {"type": "redirect", "url": download_url}


async def convert(token):
    if not isinstance(token, str):
        raise MediaExpired()
    payload = resolve_token(token)
    if payload.get("k") != "audio":
        raise ValidationError()
    url = payload.get("u", "")
    title = payload.get("t", "audio")
    if config.local_converter_available():
        tmpdir = tempfile.mkdtemp(dir=config.TEMP_DIR, prefix="mp3_")
        src_path = os.path.join(tmpdir, "source")
        out_path = os.path.join(tmpdir, "output.mp3")
        try:
            await _download_source(url, src_path)
            await _run_ffmpeg(config.resolve_ffmpeg(), src_path, out_path, title)
        except Exception:
            utils.cleanup_dir(tmpdir)
            raise
        utils.cleanup_path(src_path)
        filename = utils.safe_filename("%s_192kbps" % title, "mp3")
        return {"type": "file", "path": out_path, "tmpdir": tmpdir, "filename": filename}
    return await _remote_convert(url, title)
