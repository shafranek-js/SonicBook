import asyncio
import importlib
import os


def test_main_module_import_smoke():
    main_module = importlib.import_module("main")
    assert main_module.app is not None


def test_config_runtime_paths_initialized():
    main_module = importlib.import_module("main")
    assert isinstance(main_module.config.DOWNLOADS_DIR, str)
    assert main_module.config.DOWNLOADS_DIR != ""
    assert os.path.isdir(main_module.config.DOWNLOADS_DIR)


def test_index_handler_returns_html():
    main_module = importlib.import_module("main")
    html_content = asyncio.run(main_module.index())
    assert isinstance(html_content, str)
    assert "<html" in html_content.lower()
