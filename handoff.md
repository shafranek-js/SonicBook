# 🏗️ SonicBook Architecture & Handoff

This document provides a comprehensive overview of the **SonicBook** project architecture, current state of the codebase, setup requirements, and details about recent refactorings. It serves as a guide for future development and maintenance.

## 1. System Architecture Overview

SonicBook is an asynchronous web application built on **FastAPI**. Its primary goal is to scrape audiobook metadata (titles, chapters, stream URLs) and download fragmented audio streams (HLS/m3u8) concurrently at high speed.

### Core Components

-   **`main.py` (The Entry Point):**
    -   Serves the FastAPI web application.
    -   Manages the API endpoints (`/api/info`, `/api/download`, `/api/progress/{task_id}`, `/api/files/{file_name}`).
    -   Maintains an in-memory `progress_store` to track active download tasks.
    -   Runs a background `cleanup_task` within the FastAPI `lifespan` to periodically delete old downloaded files and clear stale progress data, preventing disk and memory leaks.
    -   Serves the frontend UI (`index.html`).

-   **`scraper.py` (Metadata Extraction):**
    -   Responsible for fetching book info from the target URL.
    -   **Primary Strategy:** Uses `httpx` with `http2=True` (requiring `h2` package) and `BeautifulSoup4` for high-speed, direct HTML parsing.
    -   **Fallback Strategy:** If the site relies heavily on JavaScript rendering or blocks simple HTTP requests, it falls back to **Playwright (Chromium)**. Playwright spins up a headless browser, executes the JS (e.g., clicking a play button), intercepts network requests to find the `.m3u8` stream, and scrapes chapter metadata directly from the DOM.

-   **`processor.py` (The Heavy Lifter):**
    -   Handles the actual downloading and assembly of audio files.
    -   **Standard Downloads (`m3u8`):** Utilizes the `yt_dlp` Python API running in a separate thread (via `run_in_executor`) to avoid blocking the `asyncio` event loop. It downloads fragments concurrently (up to 16 threads).
    -   **Direct URLs (Fallback):** Contains custom async logic using `httpx` and `aiofiles` to download direct MP3 links concurrently with retries and timeout protection.
    -   **Progress Hook:** Uses a custom `yt_dlp` progress hook that debounces updates (max 2 times per second) and sends accurate percentage data back to the `main.py` `progress_store` thread-safely.
    -   **Audio Processing (FFmpeg):** Depending on the user's choice:
        -   *M4B Mode:* Writes a temporary FFmpeg metadata file with chapter timestamps and uses FFmpeg to mux the downloaded stream into a single `.m4b` file with chapter markers.
        -   *ZIP Mode:* Uses FFmpeg to slice the downloaded stream into individual chapter files (`-ss` and `-t` flags) and bundles them into a ZIP archive using the standard `zipfile` module.
        -   *Single File Mode:* Just renames the final merged file.

-   **`config.py` (Configuration):**
    -   Stores paths (e.g., to the `downloads` directory, logs).
    -   Holds references to system dependencies (FFmpeg/FFprobe paths).
    -   Defines retention limits (`FILE_EXPIRE_SECONDS`, `STORE_EXPIRE_SECONDS`).

-   **`index.html` (Frontend):**
    -   A single-page vanilla HTML/CSS/JS frontend.
    -   Uses long-polling (via `setInterval`) to query `/api/progress/` and update the UI dynamically (progress bar, fragment count, current state).
    -   Supports Dark/Light themes and EN/RU localization.

---

## 2. System Requirements & Setup

To run SonicBook successfully, specific system-level dependencies must be installed.

### Dependencies

1.  **Python 3.10+**: Core language.
2.  **FFmpeg & FFprobe**: Absolutely critical for audio manipulation, metadata injection, and duration extraction. These **must** be installed and accessible via system PATH, or their absolute paths must be explicitly defined in `config.py`.
    *   *Windows:* `winget install -e --id Gyan.FFmpeg`
    *   *macOS:* `brew install ffmpeg`
    *   *Linux:* `sudo apt install ffmpeg`
3.  **Playwright Browsers**: Required for the fallback scraper.
    *   Installation: `playwright install chromium`

### Python Packages (from `requirements.txt`)
-   `fastapi`, `uvicorn` (Web server framework)
-   `pydantic` (Data validation)
-   `httpx[http2]` (Fast HTTP client with HTTP/2 support for scraping)
-   `beautifulsoup4` (HTML parsing)
-   `playwright` (Headless browser automation)
-   `yt-dlp` (Stream downloading engine)
-   `aiofiles` (Non-blocking asynchronous file I/O)

### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/shafranek-js/SonicBook.git
cd SonicBook

# 2. Install Python packages
pip install -r requirements.txt

# 3. Install Playwright browser
playwright install chromium

# 4. Ensure FFmpeg is installed (see above)

# 5. Run the application
python main.py
```
*The app will be available at `http://localhost:8000`.*

---

## 3. Current State of the Codebase

The codebase has recently undergone a major refactoring phase aimed at improving performance, stability, and UI/UX.

### Recent Refactoring Highlights:
*   **Async Event Loop Optimization:** Migrated heavy file writes (like `index.html` serving and direct URL downloads) to `aiofiles`. Replaced the deprecated FastAPI `@app.on_event("startup")` with the modern `@asynccontextmanager lifespan`.
*   **yt-dlp Integration:** Moved away from launching `yt-dlp` as an external subprocess and parsing its `stdout` via Regex (which caused UI progress freezing). It now correctly utilizes the `yt_dlp.YoutubeDL` Python API, wrapped in a thread executor with a debounced `progress_hook` for precise, thread-safe UI updates.
*   **Scraper Improvements:** Fixed `httpx` HTTP/2 errors by ensuring the `h2` package is requested via `httpx[http2]`.
*   **UI/UX Polish:** Added detailed visual states during processing (e.g., "Assembling M4B" with a distinct visual shimmer) so users don't think the app is frozen at 100%. Implemented proper form resetting after a task completes, allowing continuous usage without page reloads.

### Areas for Future Improvement / Technical Debt:
1.  **Playwright Persistence:** Currently, the fallback scraper (`async with async_playwright()`) spins up a new Chromium context for *every* failed `httpx` request. While this prevents memory leaks, it adds significant overhead (seconds) to the initial scraping phase. A future improvement could involve managing a persistent browser context pool within the FastAPI `lifespan`.
2.  **In-Memory State (`progress_store`):** The application state (download progress) is stored in a standard Python dictionary. This works perfectly for a single-worker deployment (`python main.py`), but will break if deployed using Gunicorn/Uvicorn with multiple workers (`--workers 4`), as memory won't be shared. Moving this to a lightweight Redis or Memcached instance would make the app horizontally scalable.
3.  **Config Management:** Hardcoded FFmpeg paths are occasionally required on Windows depending on how Winget configured the system aliases. A `.env` file approach (using `python-dotenv`) would make configuration cleaner across different deployment environments.

---
*Document generated on 16 March 2026.*