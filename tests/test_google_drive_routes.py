from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.google_drive_routes as google_drive_routes
from routes.google_drive_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_google_drive_status_route_returns_service_status(monkeypatch):
    monkeypatch.setattr(
        google_drive_routes.google_drive_service,
        "get_google_drive_status",
        lambda: {
            "configured": True,
            "connected": True,
            "folder_id": "folder123",
            "account_email": "user@example.com",
            "account_name": "User",
            "expires_at": 123.45,
            "expired": False,
        },
    )

    with _make_client() as client:
        response = client.get("/api/google-drive/status")

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["folder_id"] == "folder123"


def test_google_drive_auth_url_route_handles_runtime_error(monkeypatch):
    def fail():
        raise RuntimeError("OAuth is not configured")

    monkeypatch.setattr(google_drive_routes.google_drive_service, "build_google_drive_auth_url", fail)

    with _make_client() as client:
        response = client.get("/api/google-drive/auth/url")

    assert response.status_code == 400
    assert response.json()["detail"] == "OAuth is not configured"


def test_google_drive_import_route_returns_import_result(monkeypatch):
    async def fake_import(file_id, metadata_file_id="", cover_file_id=""):
        return {
            "file_name": "Book.m4b",
            "metadata_name": "Book.json",
            "cover_name": "Book.jpg",
        }

    monkeypatch.setattr(google_drive_routes.google_drive_service, "import_google_drive_file", fake_import)

    with _make_client() as client:
        response = client.post(
            "/api/google-drive/import",
            json={"file_id": "file123", "metadata_file_id": "meta123", "cover_file_id": "cover123"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "file_name": "Book.m4b",
        "metadata_name": "Book.json",
        "cover_name": "Book.jpg",
    }


def test_google_drive_library_route_preserves_streamable_flag(monkeypatch):
    async def fake_library(folder_id="", force_refresh=False):
        return [
            {
                "name": "Book.m4b",
                "book_id": "book:file:book:123",
                "size_bytes": 123,
                "size_mb": 0.12,
                "has_meta": True,
                "duration_seconds": 42.0,
                "chapter_count": 2,
                "mtime": 1.0,
                "source": "google_drive",
                "drive_file_id": "file123",
                "drive_metadata_file_id": "meta123",
                "drive_cover_file_id": "cover123",
                "mime_type": "audio/mp4",
                "web_view_link": "https://drive.google.com/file/d/file123/view",
                "streamable": True,
            }
        ]

    monkeypatch.setattr(
        google_drive_routes.google_drive_service,
        "list_google_drive_library_files_cached",
        fake_library,
    )

    with _make_client() as client:
        response = client.get("/api/google-drive/library")

    assert response.status_code == 200
    assert response.json()["files"][0]["streamable"] is True


def test_google_drive_metadata_route_returns_playback_payload(monkeypatch):
    async def fake_metadata(file_id, metadata_file_id="", cover_file_id=""):
        return {
            "title": "Drive Book",
            "mode": "single",
            "file_name": "Drive Book.m4b",
            "book_id": "book:file:drive-book:123",
            "source": "google_drive",
            "chapters": [{"title": "One", "start": 0, "end": 10}],
            "stream_url": f"/api/google-drive/files/{file_id}/stream",
        }

    monkeypatch.setattr(google_drive_routes.google_drive_service, "build_google_drive_metadata", fake_metadata)

    with _make_client() as client:
        response = client.get("/api/google-drive/metadata/file123")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "google_drive"
    assert body["chapters"][0]["title"] == "One"
