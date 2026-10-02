import os

APP_NAME = "RIKA MEDIA DOWNLOADER"

TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))

MIN_REQUEST_INTERVAL = float(os.environ.get("MIN_REQUEST_INTERVAL", "0"))

ENABLE_ABUSE_BLOCK = os.environ.get("ENABLE_ABUSE_BLOCK", "1") == "1"

ABUSE_THRESHOLD = int(os.environ.get("ABUSE_THRESHOLD", "60"))

ABUSE_BLOCK_SECONDS = int(os.environ.get("ABUSE_BLOCK_SECONDS", "600"))
