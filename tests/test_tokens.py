import time

import pytest

from core import utils
from core.exceptions import MediaExpired


def test_token_roundtrip():
    payload = {"u": "https://redirector.googlevideo.com/x", "k": "video"}
    token = utils.issue_token(payload)
    assert isinstance(token, str)
    assert len(token) > 50
    data = utils.verify_token(token)
    assert data is not None
    assert data["u"] == payload["u"]
    assert data["k"] == "video"
    assert "exp" in data


def test_token_tamper_rejected():
    token = utils.issue_token({"u": "https://redirector.googlevideo.com/x"})
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert utils.verify_token(tampered) is None


def test_token_garbage_rejected():
    assert utils.verify_token("") is None
    assert utils.verify_token(None) is None
    assert utils.verify_token("not-a-token") is None


def test_token_expiry_rejected(monkeypatch):
    import core.config as config
    import core.utils as utils_mod
    monkeypatch.setattr(config, "TOKEN_TTL", 3600)
    token = utils.issue_token({"u": "https://redirector.googlevideo.com/x"})
    assert utils.verify_token(token) is not None
    real_time = time.time
    monkeypatch.setattr(utils_mod.time, "time", lambda: real_time() + 7200)
    assert utils.verify_token(token) is None


def test_token_no_url_rejected():
    token = utils.issue_token({"k": "video"})
    assert utils.verify_token(token) is None


def test_expired_media_raises():
    from handler.download_handler import resolve_token
    with pytest.raises(MediaExpired):
        resolve_token("garbage-token")
