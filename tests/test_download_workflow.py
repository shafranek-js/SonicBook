import download_workflow


def test_book_info_cache_roundtrip_and_invalidate(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(download_workflow.time, "time", lambda: now)
    download_workflow.book_info_cache.clear()

    download_workflow.cache_book_info(
        "https://example.com/book",
        m3u8="https://example.com/stream.m3u8",
        title="Example Book",
        chapters=[{"title": "Chapter 1", "start": 0, "end": 10}],
        cover="https://example.com/cover.jpg",
    )

    cached = download_workflow.get_cached_book_info("https://example.com/book")
    assert cached["title"] == "Example Book"
    assert cached["m3u8"] == "https://example.com/stream.m3u8"

    download_workflow.invalidate_book_info("https://example.com/book")
    assert download_workflow.get_cached_book_info("https://example.com/book") is None


def test_book_info_cache_expires(monkeypatch):
    now = 2000.0
    monkeypatch.setattr(download_workflow.time, "time", lambda: now)
    download_workflow.book_info_cache.clear()

    download_workflow.cache_book_info(
        "https://example.com/book",
        m3u8="stream",
        title="Expired Book",
        chapters=[],
        cover=None,
    )

    monkeypatch.setattr(
        download_workflow.time,
        "time",
        lambda: now + download_workflow.BOOK_INFO_CACHE_TTL_SECONDS + 1,
    )

    assert download_workflow.get_cached_book_info("https://example.com/book") is None

