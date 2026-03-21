from fastapi import FastAPI
from fastapi.testclient import TestClient

import bookmark_service
from routes.bookmark_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_bookmark_allows_null_payload(monkeypatch):
    monkeypatch.setattr(bookmark_service, "get_bookmark", lambda book_id: None)

    with _make_client() as client:
        response = client.get("/api/bookmarks/book:file:missing:1")

    assert response.status_code == 200
    assert response.json() == {"bookmark": None}
