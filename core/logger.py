import logging
import os
import re


_MASK_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s&;]{8,})"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(cookie\s*[:=]\s*)([^\s&;]+)"),
    re.compile(r"(?i)(sig(nature)?=[^&\s]{16,})"),
    re.compile(r"(?i)(pot=[^&\s]{16,})"),
]


def mask_secrets(text):
    if not isinstance(text, str):
        text = str(text)
    masked = text
    for pattern in _MASK_PATTERNS:
        masked = pattern.sub(lambda m: m.group(1) + "***", masked)
    for name in ("SECRET_KEY", "CONVERTER_API_KEY", "BOT_TOKEN"):
        value = os.environ.get(name, "")
        if value and len(value) > 4 and value in masked:
            masked = masked.replace(value, "***")
    return masked


class SecretMaskFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = mask_secrets(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler.addFilter(SecretMaskFilter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
