VIDEO_EXTENSIONS = {"mp4", "webm", "mkv", "3gp"}

AUDIO_EXTENSIONS = {"m4a", "weba", "webm", "aac", "mp3", "opus", "ogg"}

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

DOWNLOAD_HOST_EXACT = {
    "redirector.googlevideo.com",
}

DOWNLOAD_HOST_SUFFIXES = (
    ".googlevideo.com",
    ".fbcdn.net",
    ".xhcdn.com",
)

THUMBNAIL_HOST_SUFFIXES = (
    ".ytimg.com",
    ".youtube.com",
)

BLOCKED_SCHEMES = {
    "file",
    "ftp",
    "gopher",
    "data",
    "javascript",
    "jar",
    "ldap",
    "dict",
}

BLOCKED_HOSTS = {
    "localhost",
}

QUALITY_RANK = {
    "4320p": 4320,
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "240p": 240,
    "144p": 144,
}

K_LABELS = {
    "8": "4320p",
    "4": "2160p",
    "2": "1440p",
}

UPSTREAM_TIMEOUT = 25.0
COBALT_TIMEOUT = 30.0
DOWNLOAD_TIMEOUT = 60.0
FFMPEG_TIMEOUT = 180.0

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

GENERIC_ERROR = "Unable to process this request."
