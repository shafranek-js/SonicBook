import importlib

import bookmark_service


def test_canonical_bookmark_reads_legacy_stored_entry(tmp_path, monkeypatch):
    bookmark_file = tmp_path / "bookmarks.json"
    monkeypatch.setattr(bookmark_service, "BOOKMARKS_FILE", str(bookmark_file))

    legacy_id = bookmark_service.build_legacy_book_id("Example Book.m4b")
    bookmark_service.save_bookmarks(
        {
            legacy_id: {
                "time": 10.25,
                "duration": 120.0,
                "track": 1,
                "file_name": "Example Book.m4b",
                "source": "local",
            }
        }
    )

    book_id = bookmark_service.build_book_id("Example Book.m4b", size_bytes=123)
    loaded = bookmark_service.get_bookmark(book_id)
    assert loaded["file_name"] == "Example Book.m4b"
    assert loaded["track"] == 1


def test_delete_bookmark_removes_all_aliases(tmp_path, monkeypatch):
    bookmark_file = tmp_path / "bookmarks.json"
    monkeypatch.setattr(bookmark_service, "BOOKMARKS_FILE", str(bookmark_file))

    canonical = bookmark_service.build_book_id("Alias Book.m4b", size_bytes=456)
    bookmark_service.save_bookmark(canonical, {"time": 5, "duration": 10, "track": 0})

    assert bookmark_service.delete_bookmark(canonical) is True
    assert bookmark_service.get_bookmark(canonical) is None
    assert bookmark_service.get_bookmark(bookmark_service.build_legacy_book_id("Alias Book.m4b")) is None
