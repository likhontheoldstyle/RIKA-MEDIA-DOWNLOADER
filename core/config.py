import functools
import os
import shutil
import tempfile


def _env(name, default=""):
    value = os.environ.get(name, default)
    return value if isinstance(value, str) else default


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


APP_ENV = _env("APP_ENV", "production")
SECRET_KEY = "rx_zrNY09MxlMwEn-43ZEQjaCp7zsMrlI07Ojrj2oWjpBlZDxTRG6NL7EK9TmP89"
YTDL_API_URL = _env("YTDL_API_URL", "https://api.ytultra.com/ikool/youtube/download")
FFMPEG_PATH = _env("FFMPEG_PATH", "")
CONVERTER_URL = _env("CONVERTER_URL", "")
CONVERTER_API_KEY = _env("CONVERTER_API_KEY", "")
RATE_LIMIT = _env_int("RATE_LIMIT", 10)
MP3_RATE_LIMIT = _env_int("MP3_RATE_LIMIT", 3)
CACHE_TTL = _env_int("CACHE_TTL", 600)
TOKEN_TTL = _env_int("TOKEN_TTL", 2700)
MAX_REQUEST_SIZE = _env_int("MAX_REQUEST_SIZE", 1048576)
MAX_URL_LENGTH = _env_int("MAX_URL_LENGTH", 2048)
MP3_BITRATE = _env("MP3_BITRATE", "192k")
MP3_MAX_SOURCE_BYTES = _env_int("MP3_MAX_SOURCE_BYTES", 262144000)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_temp_dir():
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return tempfile.gettempdir()
    return os.path.join(BASE_DIR, "var", "temp")


TEMP_DIR = _env("TEMP_DIR", "") or _default_temp_dir()


@functools.lru_cache(maxsize=1)
def resolve_ffmpeg():
    if FFMPEG_PATH:
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            return FFMPEG_PATH
        return ""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        return ""
    return ""


def local_converter_available():
    return bool(resolve_ffmpeg())


def remote_converter_available():
    return bool(CONVERTER_URL)


def mp3_available():
    return bool(local_converter_available() or remote_converter_available())
