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
  - Implement symmetric sliding panels: Library on the left, Chapters on the right.
- [x] **Step 4: Frontend Player Logic (JavaScript):**
  - Implement core audio playback and seek functionality.
  - Fetch and parse the JSON metadata to draw chapter markers on the timeline.
  - Add interactive chapter progress bars and dynamic timers in the side panel.
  - Implement `localStorage` bookmarks to save playback position and track per book.
  - Add playlist logic for `ZIP` mode (playing multiple files sequentially).
  - Add UI state persistence across page reloads (open panels, last book, mode).
  - Implement dynamic Play/Pause icon syncing in the library list.

## ✨ Version 1.1 Features (Polishing & UX)
- [x] 1. **Library Search:** Add a real-time JS-based search input to the "My Library" panel to quickly filter downloaded books.
- [ ] 2. **Book Covers:**
  - Update `scraper.py` to extract the high-resolution cover image URL.
  - Update `processor.py` to download and save the cover as `[book_name].jpg`.
  - Update the UI to display the cover image cleanly below or alongside the central player.
- [ ] 3. **Keyboard Shortcuts:** Add global hotkeys (Space for Play/Pause, Left/Right arrows for 15s seek).
- [ ] 4. **Media Session API:** Integrate `navigator.mediaSession` to allow users to control playback from their OS media widget, lock screen, or physical media keys, complete with metadata (title, artist, cover art).
- [x] 1. **Async ZIP Extraction:** Fix event loop blocking in `main.py` by moving `zipfile.extractall` to a separate thread executor.
- [x] 2. **Race Condition Protection:** Add `asyncio.Lock` for ZIP extraction to prevent filesystem corruption on concurrent requests.
- [x] 3. **Frontend Componentization:** Extract CSS and JS from `index.html` into `static/style.css` and `static/app.js` for better maintainability and caching.
- [x] 4. **Playwright Optimization:** Initialize a single persistent browser context in FastAPI `lifespan` instead of launching a new one per request.
- [x] 5. **Subprocess Timeouts:** Add strict `asyncio.wait_for` timeouts to `yt-dlp` and `ffmpeg` execution to prevent memory/process leaks on network hangs.
- [x] 6. **Modernize Progress Delivery:** Replace polling (`setInterval`) with Server-Sent Events (SSE) or WebSockets for real-time progress updates without DDoS-ing the server.
- [ ] 7. **State Management:** Migrate `progress_store` to Redis for multi-worker support (Optional/Advanced).
