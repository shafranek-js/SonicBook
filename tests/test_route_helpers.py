import pytest
from fastapi import HTTPException

from route_helpers import build_user_error_message, resolve_download_path, validate_book_url


def test_validate_book_url_accepts_http_and_https():
    assert validate_book_url("https://example.com/book") == "https://example.com/book"
    assert validate_book_url("http://example.com/book") == "http://example.com/book"


def test_validate_book_url_rejects_invalid_scheme():
    with pytest.raises(HTTPException) as exc:
        validate_book_url("ftp://example.com/book")
    assert exc.value.status_code == 400


def test_resolve_download_path_rejects_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DOWNLOADS_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        resolve_download_path("..\\outside.mp3")
    assert exc.value.status_code == 400


def test_build_user_error_message_prefers_exception_text():
    assert build_user_error_message(RuntimeError("Explicit failure"), "fallback") == "Explicit failure"
    assert build_user_error_message(RuntimeError("   "), "fallback") == "fallback"

