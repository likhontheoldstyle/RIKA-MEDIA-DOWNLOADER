from urllib.parse import urlparse

PLATFORM_HOSTS = {
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "youtu.be": "youtube",
    "music.youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "m.tiktok.com": "tiktok",
    "vm.tiktok.com": "tiktok",
    "vt.tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "fb.watch": "facebook",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    "mobile.twitter.com": "twitter",
    "xhamster.com": "xhamster",
    "www.xhamster.com": "xhamster",
}

PLATFORM_NAMES = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "X (Twitter)",
    "xhamster": "xHamster",
    "unknown": "Video",
}

COBALT_PLATFORMS = {"tiktok", "instagram", "twitter"}


def detect_platform(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "unknown"
    if not host:
        return "unknown"
    if host in PLATFORM_HOSTS:
        return PLATFORM_HOSTS[host]
    for suffix in ("tiktok.com", "instagram.com", "facebook.com", "twitter.com", "x.com", "xhamster.com"):
        if host.endswith("." + suffix):
            return PLATFORM_HOSTS.get(suffix, "unknown")
    return "unknown"


def platform_display_name(platform):
    return PLATFORM_NAMES.get(platform, "Video")


def uses_cobalt(platform):
    return platform in COBALT_PLATFORMS
