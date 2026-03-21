import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.library_routes as library_routes
from routes.library_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_imported_book_ids_route_returns_lightweight_list(monkeypatch):
    monkeypatch.setattr(library_routes.library_service, "list_library_book_ids", lambda folder: ["book:1", "book:2"])

    with _make_client() as client:
        response = client.get("/api/library/imported-book-ids")

    assert response.status_code == 200
    assert response.json() == {"book_ids": ["book:1", "book:2"]}


def test_download_file_returns_404_for_missing_file(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing.m4b"
    monkeypatch.setattr(library_routes, "resolve_download_path", lambda file_name: str(missing_path))

    with _make_client() as client:
        response = client.get("/api/files/missing.m4b")

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_metadata_route_reads_json_sidecar(monkeypatch, tmp_path):
    audio_path = tmp_path / "Book.m4b"
    audio_path.write_bytes(b"audio")
    json_path = tmp_path / "Book.json"
    json_path.write_text(json.dumps({"title": "Book", "chapters": []}), encoding="utf-8")

    monkeypatch.setattr(library_routes, "resolve_download_path", lambda file_name: str(audio_path))

    with _make_client() as client:
        response = client.get("/api/metadata/Book.m4b")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Book"
    assert body["book_id"].startswith("book:file:")


def test_metadata_route_returns_zip_playlist_payload(monkeypatch, tmp_path):
    zip_path = tmp_path / "Book.zip"
    zip_path.write_bytes(b"zip")

    async def fake_zip_metadata(file_path, file_name, downloads_dir):
        return {
            "title": "Book",
            "mode": "zip",
            "playlist": [{"title": "001", "file": ".extracted_Book/001.mp3"}],
        }

    monkeypatch.setattr(library_routes, "resolve_download_path", lambda file_name: str(zip_path))
    monkeypatch.setattr(library_routes.zip_service, "build_zip_metadata", fake_zip_metadata)

    with _make_client() as client:
        response = client.get("/api/metadata/Book.zip")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "zip"
    assert body["playlist"][0]["file"].endswith("001.mp3")
