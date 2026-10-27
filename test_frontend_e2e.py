import socket
import threading
import time
import urllib.request

import pytest
import uvicorn


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_seconds: float = 10.0):
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Server did not start: {last_error}")


@pytest.fixture()
def sonicbook_server(tmp_path, monkeypatch):
    import bookmark_service
    import config
    import library_service
    import main
    import progress_service

    downloads_dir = tmp_path / "downloads"
    work_dir = tmp_path / "work"
    downloads_dir.mkdir()
    (downloads_dir / "sample_e2e_book.mp3").write_bytes(b"dummy audio data")

    monkeypatch.setattr(config, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(config, "DOWNLOADS_DIR", str(downloads_dir))
    monkeypatch.setattr(config, "DEFAULT_DOWNLOADS_DIR", str(downloads_dir))
    monkeypatch.setitem(config.DEFAULT_SETTINGS, "downloads_dir", str(downloads_dir))
    monkeypatch.setattr(config, "WORK_DIR", str(work_dir))
    monkeypatch.setattr(bookmark_service, "LEGACY_BOOKMARKS_FILE", str(tmp_path / "bookmarks.json"))
    monkeypatch.setattr(library_service, "LIBRARY_INDEX_FILE", str(tmp_path / "library_index.json"))
    monkeypatch.setattr(progress_service, "PROGRESS_STORE_FILE", str(tmp_path / "progress_store.json"))
    progress_service.progress_store.clear()
    bookmark_service._state_cache = None
    bookmark_service._state_cache_mtime = 0

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            main.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    _wait_for_server(base_url)

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_frontend_shell_settings_sleep_timer_and_library_sources(sonicbook_server):
    try:
        from playwright.sync_api import expect, sync_playwright
    except ImportError as exc:
        pytest.skip(f"Playwright is not installed: {exc}")

    console_errors = []
    page_errors = []

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")

        context = browser.new_context()
        page = context.new_page()
        page.route(
            "**/api/google-drive/library**",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"files":[]}',
            ),
        )
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        page.goto(sonicbook_server, wait_until="domcontentloaded")
        expect(page.locator("#appContainer")).to_be_visible()
        expect(page.locator(".toolbar-link")).to_be_visible()
        expect(page.locator("[data-testid='settings-button']")).to_be_visible()

        page.locator("#libBtn").click()
        expect(page.locator("#libraryPanel")).to_be_visible()
        expect(page.locator("#libraryList")).to_be_visible()
        row = page.locator(".library-item").first
        row.hover()
        delete_btn = page.locator("[data-library-action='delete']").first
        expect(delete_btn).to_be_visible()
        page.once("dialog", lambda dialog: dialog.accept())
        delete_btn.click()
        expect(page.locator("[data-library-action='delete']")).not_to_be_visible()

        page.locator("[data-testid='settings-button']").click()
        settings_menu = page.locator("[data-testid='settings-menu']")
        expect(settings_menu).to_be_visible()
        expect(page.locator("#t-google-drive-label")).to_contain_text("Google Drive")
        expect(page.locator("#t-playback-profile-label")).to_contain_text("Sync profile")
        expect(page.locator("#t-sleep-timer-min-brightness-label")).to_be_visible()

        settings_style = settings_menu.evaluate(
            "(el) => ({ backgroundColor: getComputedStyle(el).backgroundColor, opacity: getComputedStyle(el).opacity })"
        )
        assert settings_style["opacity"] == "1"
        assert settings_style["backgroundColor"] != "rgba(0, 0, 0, 0)"

        min_brightness = page.locator("[data-testid='sleep-timer-min-brightness']")
        min_brightness.fill("22")
        min_brightness.press("Tab")
        page.wait_for_function("localStorage.getItem('sleep-timer-min-brightness') === '22'")

        sleep_timer = page.locator("[data-testid='sleep-timer-button']")
        sleep_timer.click()
        expect(sleep_timer).to_have_attribute("aria-pressed", "true")
        expect(page.locator("#sleepTimerCountdown")).to_be_visible()
        sleep_timer.click()
        expect(sleep_timer).to_have_attribute("aria-pressed", "false")

        page.locator("[data-testid='settings-button']").click()
        page.locator("[data-testid='library-source-drive']").click()
        assert "active" in (page.locator("[data-testid='library-source-drive']").get_attribute("class") or "")
        page.locator("[data-testid='library-source-local']").click()
        assert "active" in (page.locator("[data-testid='library-source-local']").get_attribute("class") or "")

        folder_payload = page.evaluate(
            "fetch('/api/settings/folder').then((response) => response.json())"
        )
        assert "downloads" in folder_payload["folder"]

        context.close()
        browser.close()

    assert console_errors == []
    assert page_errors == []
