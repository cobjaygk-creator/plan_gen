from app.media_cache import THUMBNAIL_DIR, is_cached_thumbnail_missing


def test_is_cached_thumbnail_missing_true_for_absent_local_file():
    assert is_cached_thumbnail_missing("data/thumbnails/event_bench/does-not-exist.png") is True


def test_is_cached_thumbnail_missing_false_when_file_present(tmp_path, monkeypatch):
    monkeypatch.setattr("app.media_cache.THUMBNAIL_DIR", tmp_path)
    dest = tmp_path / "event_bench" / "real.png"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"fake-image-bytes")
    assert is_cached_thumbnail_missing("data/thumbnails/event_bench/real.png") is False


def test_is_cached_thumbnail_missing_false_for_external_url():
    assert is_cached_thumbnail_missing("https://cdn.example.com/x.png") is False
    assert is_cached_thumbnail_missing("http://cdn.example.com/x.png") is False


def test_is_cached_thumbnail_missing_false_for_empty_value():
    assert is_cached_thumbnail_missing(None) is False
    assert is_cached_thumbnail_missing("") is False
