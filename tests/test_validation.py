import pytest

from core.exceptions import InvalidURL, UnsupportedPlatform
from security.validation import extract_video_id


def test_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_short_url():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_shorts_url():
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_embed_url():
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_mobile_url():
    assert extract_video_id("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=10s") == "dQw4w9WgXcQ"


def test_non_youtube_rejected():
    with pytest.raises(UnsupportedPlatform):
        extract_video_id("https://vimeo.com/123456")


def test_localhost_rejected():
    with pytest.raises((InvalidURL, UnsupportedPlatform)):
        extract_video_id("http://localhost/watch?v=dQw4w9WgXcQ")


def test_private_ip_rejected():
    with pytest.raises((InvalidURL, UnsupportedPlatform)):
        extract_video_id("http://192.168.1.1/watch?v=dQw4w9WgXcQ")


def test_bad_scheme_rejected():
    with pytest.raises(InvalidURL):
        extract_video_id("javascript:alert(1)")


def test_file_scheme_rejected():
    with pytest.raises(InvalidURL):
        extract_video_id("file:///etc/passwd")


def test_missing_id_rejected():
    with pytest.raises(InvalidURL):
        extract_video_id("https://www.youtube.com/watch")


def test_empty_rejected():
    with pytest.raises(InvalidURL):
        extract_video_id("")


def test_oversize_rejected():
    with pytest.raises(InvalidURL):
        extract_video_id("https://www.youtube.com/watch?v=" + "a" * 3000)
