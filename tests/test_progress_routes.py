from fastapi import FastAPI
from fastapi.testclient import TestClient

import progress_service
from routes.progress_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_progress_returns_progress_payload(monkeypatch):
    monkeypatch.setattr(
        progress_service,
        "get_progress",
        lambda task_id: {
            "status": "processing",
            "phase": "downloading",
            "percent": 42.5,
            "current_frag": 3,
            "total_frags": 10,
            "file_name": "",
            "source_url": "https://example.com/book",
            "mode": "m4b",
            "message": "",
            "updated_at": 123.0,
        },
    )

    with _make_client() as client:
        response = client.get("/api/progress/task-1")

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["percent"] == 42.5
