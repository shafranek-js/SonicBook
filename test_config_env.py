import importlib

import config


def test_parse_env_int_uses_default_for_invalid_values(monkeypatch):
    monkeypatch.setenv("SONICBOOK_TEST_INT", "not-an-int")
    assert config.parse_env_int("SONICBOOK_TEST_INT", 16, min_value=1) == 16


def test_parse_env_int_clamps_bounds(monkeypatch):
    monkeypatch.setenv("SONICBOOK_TEST_INT", "0")
    assert config.parse_env_int("SONICBOOK_TEST_INT", 16, min_value=1) == 1

    monkeypatch.setenv("SONICBOOK_TEST_INT", "99")
    assert config.parse_env_int("SONICBOOK_TEST_INT", 4, min_value=1, max_value=8) == 8


def test_parse_env_bool_uses_default_for_invalid_values(monkeypatch):
    monkeypatch.setenv("SONICBOOK_TEST_BOOL", "maybe")
    assert config.parse_env_bool("SONICBOOK_TEST_BOOL", True) is True
    assert config.parse_env_bool("SONICBOOK_TEST_BOOL", False) is False


def test_config_reload_survives_invalid_download_env(monkeypatch):
    monkeypatch.setenv("YTDLP_CONCURRENCY", "bad")
    monkeypatch.setenv("MULTI_CONNECTION_MIN_BYTES", "bad")
    monkeypatch.setenv("MULTI_CONNECTION_MAX_SEGMENTS", "bad")
    monkeypatch.setenv("MULTI_CONNECTION_DOWNLOADS", "bad")

    reloaded = importlib.reload(config)
    try:
        assert reloaded.YTDLP_CONCURRENCY == 16
        assert reloaded.MULTI_CONNECTION_MIN_BYTES == 64 * 1024 * 1024
        assert reloaded.MULTI_CONNECTION_MAX_SEGMENTS == 4
        assert reloaded.MULTI_CONNECTION_DOWNLOADS is True
    finally:
        monkeypatch.delenv("YTDLP_CONCURRENCY", raising=False)
        monkeypatch.delenv("MULTI_CONNECTION_MIN_BYTES", raising=False)
        monkeypatch.delenv("MULTI_CONNECTION_MAX_SEGMENTS", raising=False)
        monkeypatch.delenv("MULTI_CONNECTION_DOWNLOADS", raising=False)
        importlib.reload(config)
