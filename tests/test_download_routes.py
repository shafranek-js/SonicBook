from fastapi import FastAPI
from fastapi.testclient import TestClient

import download_workflow
import progress_service
import scraper
from routes.download_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_info_route_returns_preview_and_caches(monkeypatch):
    cached_calls = []

    async def fake_get_book_info(url):
        return (
            "https://example.com/stream.m3u8",
            "Route Book",
            [{"title": "One", "start": 0, "end": 5}],
            "https://example.com/cover.jpg",
        )

    def fake_cache_book_info(book_url, **payload):
        cached_calls.append((book_url, payload))

    monkeypatch.setattr(scraper, "get_book_info", fake_get_book_info)
    monkeypatch.setattr(download_workflow, "cache_book_info", fake_cache_book_info)

    with _make_client() as client:
        response = client.post("/api/info", json={"url": "https://example.com/book"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Route Book"
    assert cached_calls[0][0] == "https://example.com/book"
    assert cached_calls[0][1]["m3u8"] == "https://example.com/stream.m3u8"


def test_download_route_reuses_existing_task(monkeypatch):
    monkeypatch.setattr(progress_service, "find_active_task_by_source", lambda url: ("task-123", {"status": "processing"}))

    with _make_client() as client:
        response = client.post("/api/download", json={"url": "https://example.com/book", "mode": "m4b"})

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-123", "reused": True}


def test_download_route_rejects_unsupported_mode():
    with _make_client() as client:
        response = client.post("/api/download", json={"url": "https://example.com/book", "mode": "wav"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported download mode."
