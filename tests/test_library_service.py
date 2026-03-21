import json

import library_service
from service_models import LibraryFileRecordModel, LibraryIndexEntryModel


def test_library_file_record_model_normalizes_numeric_fields():
    record = LibraryFileRecordModel(
        name="Book.m4b",
        size_bytes=-5,
        size_mb=-1.25,
        duration_seconds=-10,
        chapter_count=-3,
        mtime="123.45",
    )

    assert record.size_bytes == 0
    assert record.size_mb == 0.0
    assert record.duration_seconds is None
    assert record.chapter_count == 0
    assert record.mtime == 123.45


def test_library_index_entry_model_normalizes_nested_payload():
    entry = LibraryIndexEntryModel(
        size_bytes=-1,
        mtime_ns=-2,
        sidecar_mtime_ns=-3,
        file={
            "name": "Book.m4b",
            "size_bytes": "123",
            "size_mb": "1.5",
            "has_meta": True,
            "mtime": "5.5",
        },
    )

    assert entry.size_bytes == 0
    assert entry.mtime_ns == 0
    assert entry.sidecar_mtime_ns == 0
    assert entry.file.size_bytes == 123
    assert entry.file.size_mb == 1.5


def test_load_library_index_skips_invalid_entries(tmp_path, monkeypatch):
    index_file = tmp_path / "library_index.json"
    index_file.write_text(
        json.dumps(
            {
                "version": library_service.LIBRARY_INDEX_VERSION,
                "entries": {
                    "valid.m4b": {
                        "size_bytes": 100,
                        "mtime_ns": 1,
                        "sidecar_mtime_ns": 0,
                        "file": {
                            "name": "valid.m4b",
                            "book_id": "book:file:valid:100",
                            "size_bytes": 100,
                            "size_mb": 0.1,
                            "has_meta": False,
                            "mtime": 1.0,
                        },
                    },
                    "invalid.m4b": {
                        "size_bytes": "oops",
                        "mtime_ns": 1,
                        "sidecar_mtime_ns": 0,
                        "file": None,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(library_service, "LIBRARY_INDEX_FILE", str(index_file))

    payload = library_service._load_library_index()

    assert set(payload["entries"].keys()) == {"valid.m4b"}
