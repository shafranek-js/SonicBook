import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
import routes.settings_routes as settings_routes
from routes.settings_routes import router


def _make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_folder_returns_configured_downloads_dir(monkeypatch):
    monkeypatch.setattr(config, "DOWNLOADS_DIR", r"C:\Audiobooks")

    with _make_client() as client:
        response = client.get("/api/settings/folder")

    assert response.status_code == 200
    assert response.json() == {"folder": r"C:\Audiobooks"}


def test_choose_folder_returns_success_when_folder_selected(monkeypatch):
    selected_path = r"C:\NewLibrary"

    class FakeLoop:
        async def run_in_executor(self, executor, fn):
            return selected_path

    monkeypatch.setattr(settings_routes.asyncio, "get_running_loop", lambda: FakeLoop())
    monkeypatch.setattr(config, "save_downloads_dir", lambda path: True)

    response = asyncio.run(settings_routes.choose_folder())
    assert response == {"status": "success", "folder": selected_path}


def test_choose_folder_returns_cancelled_when_dialog_returns_empty(monkeypatch):
    class FakeLoop:
        async def run_in_executor(self, executor, fn):
            return ""

    monkeypatch.setattr(settings_routes.asyncio, "get_running_loop", lambda: FakeLoop())
    monkeypatch.setattr(config, "DOWNLOADS_DIR", r"C:\Audiobooks")

    response = asyncio.run(settings_routes.choose_folder())
    assert response == {"status": "cancelled", "folder": r"C:\Audiobooks"}
