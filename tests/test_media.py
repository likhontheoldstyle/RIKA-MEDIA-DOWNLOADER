from core import utils
from social.youtube import _parse_media_entry, _quality_from_format


def _entry(url, format_text, file_size=None):
    return {"url": url, "format": format_text, "fileSize": file_size}


def test_quality_1080p():
    assert _quality_from_format("1080p (77.16 MB) [.mp4]") == "1080p"


def test_quality_4k():
    assert _quality_from_format("4K (342.00 MB) [.webm]") == "2160p"


def test_quality_2k():
    assert _quality_from_format("2K (144.10 MB) [.webm]") == "1440p"


def test_quality_missing():
    assert _quality_from_format(None) == ""
    assert _quality_from_format("unknown") == ""


def test_parse_video_entry():
    url = "https://redirector.googlevideo.com/videoplayback?mime=video%2Fmp4&itag=137"
    item = _parse_media_entry(_entry(url, "1080p (77.16 MB) [.mp4]", 80911999))
    assert item["kind"] == "video"
    assert item["quality"] == "1080p"
    assert item["ext"] == "mp4"
    assert item["size_bytes"] == 80911999
    assert item["itag"] == "137"


def test_parse_audio_entry():
    url = "https://redirector.googlevideo.com/videoplayback?mime=audio%2Fmp4&itag=140"
    item = _parse_media_entry(_entry(url, "1080p (3.29 MB) [.m4a]", 3449447))
    assert item["kind"] == "audio"
    assert item["ext"] == "m4a"


def test_parse_entry_missing_size_from_format():
    url = "https://redirector.googlevideo.com/videoplayback?mime=video%2Fmp4&itag=18"
    item = _parse_media_entry(_entry(url, "360p [.mp4]", None))
    assert item["kind"] == "video"
    assert item["quality"] == "360p"
    assert item["size_bytes"] is None


def test_parse_entry_rejects_http():
    item = _parse_media_entry(_entry("http://example.com/x", "1080p [.mp4]", 10))
    assert item is None


def test_parse_entry_rejects_garbage():
    assert _parse_media_entry({}) is None
    assert _parse_media_entry(None) is None
    assert _parse_media_entry({"url": "", "format": "1080p"}) is None


def test_quality_rank_order():
    assert utils.quality_rank("2160p") > utils.quality_rank("1080p")
    assert utils.quality_rank("1080p") > utils.quality_rank("720p")
    assert utils.quality_rank("720p") > utils.quality_rank("144p")
    assert utils.quality_rank("unknown") == -1


def test_format_size():
    assert utils.format_size(113000000) == "107.77 MB"
    assert utils.format_size(2790000) == "2.66 MB"
    assert utils.format_size(512) == "512 B"
    assert utils.format_size(None) is None
    assert utils.format_size("nope") is None


def test_parse_size_text():
    value = utils.parse_size_text("1080p (77.16 MB) [.mp4]")
    assert value == int(77.16 * 1024 ** 2)
    value = utils.parse_size_text("4K (342.00 MB) [.webm]")
    assert value == int(342.00 * 1024 ** 2)
    assert utils.parse_size_text("360p [.mp4]") is None


def test_safe_filename():
    assert utils.safe_filename("Test / Movie: 2026", "mp4") == "Test_Movie_2026.mp4"
    assert ".." not in utils.safe_filename("../../etc/passwd", "mp4")
    assert "/" not in utils.safe_filename("a/b\\c", "mp4")
    assert utils.safe_filename("", "mp3").endswith(".mp3")
