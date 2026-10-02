import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import time

from cryptography.fernet import Fernet, InvalidToken

from core import config


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MULTI_SEP = re.compile(r"[._-]+")
_SIZE_RE = re.compile(r"([\d.]+)\s*([KMGT]B)", re.IGNORECASE)


def _fernet():
    raw = config.SECRET_KEY.encode("utf-8")
    try:
        key = base64.urlsafe_b64encode(raw)
        return Fernet(key)
    except Exception:
        digest = hashlib.sha256(raw).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def issue_token(payload):
    data = dict(payload)
    data["exp"] = int(time.time()) + config.TOKEN_TTL
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def verify_token(token):
    if not token or not isinstance(token, str) or len(token) > 4096:
        return None
    try:
        raw = _fernet().decrypt(token.encode("utf-8"), ttl=config.TOKEN_TTL + 300)
        data = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, KeyError):
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    if not data.get("u"):
        return None
    return data


def new_id():
    return secrets.token_urlsafe(16)


def format_size(num_bytes):
    if num_bytes is None:
        return None
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return None
    if size < 0:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    if index == 0:
        return "%d %s" % (size, units[index])
    return "%.2f %s" % (size, units[index])


def parse_size_text(text):
    if not text or not isinstance(text, str):
        return None
    match = _SIZE_RE.search(text)
    if not match:
        return None
    multipliers = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
    try:
        return int(float(match.group(1)) * multipliers[match.group(2).upper()])
    except (ValueError, KeyError):
        return None


def safe_filename(name, extension=""):
    base = _SAFE_CHARS.sub("_", str(name or "media"))
    base = _MULTI_SEP.sub("_", base).strip("._-")
    if not base:
        base = "media"
    base = base[:120]
    ext = re.sub(r"[^A-Za-z0-9]", "", str(extension or ""))[:10]
    if ext:
        return "%s.%s" % (base, ext.lower())
    return base


def quality_rank(quality):
    from core.constants import QUALITY_RANK
    if not quality:
        return -1
    text = str(quality).strip().lower()
    if text in QUALITY_RANK:
        return QUALITY_RANK[text]
    match = re.match(r"(\d{3,4})\s*p", text)
    if match:
        return int(match.group(1))
    return -1


def cleanup_path(path):
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def cleanup_dir(path):
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


class TTLCache:
    def __init__(self, ttl=600, max_items=200):
        self._ttl = ttl
        self._max_items = max_items
        self._store = {}

    def get(self, key):
        item = self._store.get(key)
        if not item:
            return None
        value, expires = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key, value):
        if len(self._store) >= self._max_items:
            oldest = min(self._store.items(), key=lambda kv: kv[1][1])[0]
            self._store.pop(oldest, None)
        self._store[key] = (value, time.time() + self._ttl)

    def clear(self):
        self._store.clear()
