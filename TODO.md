# Refactoring TODO List

- [x] 1. **FastAPI Lifespan:** Replace deprecated `@app.on_event("startup")` with `lifespan` context manager in `main.py`.
- [x] 2. **Config Paths:** Remove hardcoded local paths for FFmpeg/FFprobe in `config.py`, use just 'ffmpeg' and 'ffprobe' as defaults.
- [x] 3. **Async File I/O:** Install and use `aiofiles` for asynchronous file operations (e.g., `index.html` read in `main.py`, chunk writing in `processor.py`).
- [x] 4. **Logging:** Replace custom synchronous `log_debug` function with Python's standard `logging` module in `scraper.py` and `processor.py`.
- [x] 5. **Error Handling:** Replace empty `except: pass` blocks with proper error logging.
- [x] 6. **yt-dlp API:** Refactor `yt-dlp` execution in `processor.py` to use the Python API instead of parsing subprocess stdout.

# Feature Backlog

## 🎵 Integrated Web Player Implementation Plan
Build an advanced integrated web player to stream the downloaded audiobooks directly from the browser.

- [x] **Step 1: Backend Metadata Generation:**
  - Update `processor.py` to save a `[book_name].json` file containing book title, format, and chapter metadata (titles, start, end times) alongside the final downloaded file.
- [x] **Step 2: Backend Streaming & API:**
  - Ensure FastAPI `FileResponse` is correctly configured to support HTTP `Range` requests for streaming audio.
  - Create an endpoint to fetch the generated `.json` metadata file for a given book.
- [x] **Step 3: Frontend Player UI:**
  - Build the HTML/CSS player interface in `index.html` (cover, title, play/pause, timeline, time display).
  - Add a chapter list sidebar or modal.
- [x] **Step 4: Frontend Player Logic (JavaScript):**
  - Implement core audio playback and seek functionality.
  - Fetch and parse the JSON metadata to draw chapter markers on the timeline.
  - Implement `localStorage` bookmarks to save playback position per book.
  - Add playlist logic for `ZIP` mode (playing multiple files sequentially).

## 🛠️ Technical Debt / Optimizations
- [ ] **Playwright Optimization:** Use a persistent browser context instead of launching a new browser per request.
- [ ] **State Management:** Migrate `progress_store` to Redis for multi-worker support.