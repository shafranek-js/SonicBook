# Refactoring TODO List

- [x] 1. **FastAPI Lifespan:** Replace deprecated `@app.on_event("startup")` with `lifespan` context manager in `main.py`.
- [x] 2. **Config Paths:** Remove hardcoded local paths for FFmpeg/FFprobe in `config.py`, use just 'ffmpeg' and 'ffprobe' as defaults.
- [x] 3. **Async File I/O:** Install and use `aiofiles` for asynchronous file operations (e.g., `index.html` read in `main.py`, chunk writing in `processor.py`).
- [x] 4. **Logging:** Replace custom synchronous `log_debug` function with Python's standard `logging` module in `scraper.py` and `processor.py`.
- [x] 5. **Error Handling:** Replace empty `except: pass` blocks with proper error logging.
- [ ] 6. **yt-dlp API (Optional):** Refactor `yt-dlp` execution in `processor.py` to use the Python API instead of parsing subprocess stdout.
- [ ] 7. **Playwright Optimization (Optional):** Use a persistent browser context instead of launching a new browser per request.
