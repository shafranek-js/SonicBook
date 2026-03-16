# 🏗️ SonicBook Architecture & Handoff

This document provides a comprehensive overview of the **SonicBook** project architecture, current state of the codebase, setup requirements, and details about recent refactorings. It serves as a guide for future development and maintenance.

## 1. System Architecture Overview

SonicBook is an asynchronous web application built on **FastAPI**. Its primary goal is to scrape audiobook metadata (titles, chapters, stream URLs), download fragmented audio streams (HLS/m3u8) concurrently at high speed, and provide an integrated playback experience.

### Core Components

-   **`main.py` (The Entry Point):**
    -   Serves the FastAPI web application.
    -   Manages the API endpoints (`/api/info`, `/api/download`, `/api/progress/{task_id}`, `/api/files/{file_name}`, `/api/library`, `/api/metadata/{file_name}`).
    -   Maintains an in-memory `progress_store` to track active download tasks.
    -   Runs a background `cleanup_task` within the FastAPI `lifespan` to periodically clear stale progress data, preventing memory leaks.
    -   Serves the frontend UI (`index.html`).
    -   Handles local directory selection via an integrated `tkinter` dialog.

-   **`scraper.py` (Metadata Extraction):**
    -   Responsible for fetching book info from the target URL.
    -   **Primary Strategy:** Uses `httpx` with `http2=True` (requiring `h2` package) and `BeautifulSoup4` for high-speed, direct HTML parsing.
    -   **Fallback Strategy:** If the site relies heavily on JavaScript rendering or blocks simple HTTP requests, it falls back to **Playwright (Chromium)**. Playwright spins up a headless browser, executes the JS (e.g., clicking a play button), intercepts network requests to find the `.m3u8` stream, and scrapes chapter metadata directly from the DOM.

-   **`processor.py` (The Heavy Lifter):**
    -   Handles the actual downloading and assembly of audio files.
    -   **Standard Downloads (`m3u8`):** Utilizes the `yt_dlp` Python API running in a separate thread (via `run_in_executor`) to avoid blocking the `asyncio` event loop. It downloads fragments concurrently (up to 16 threads).
    -   **Progress Hook:** Uses a custom `yt_dlp` progress hook that debounces updates (max 2 times per second) and sends accurate percentage data back to the `main.py` `progress_store` thread-safely.
    -   **Audio Processing (FFmpeg):** Depending on the user's choice:
        -   *M4B Mode:* Writes a temporary FFmpeg metadata file with chapter timestamps and uses FFmpeg to mux the downloaded stream into a single `.m4b` file with chapter markers.
        -   *ZIP Mode:* Uses FFmpeg to slice the downloaded stream into individual chapter files (`-ss` and `-t` flags) and bundles them into a ZIP archive using the standard `zipfile` module.
    -   **Metadata Generation:** Generates a lightweight `.json` file alongside the completed audio file containing the exact chapter timings and titles, which is crucial for the web player's navigation.

-   **`config.py` (Configuration):**
    -   Stores dynamic paths loaded from a local `settings.json` file.
    -   Holds references to system dependencies (FFmpeg/FFprobe paths).

-   **`index.html` (Frontend):**
    -   A single-page vanilla HTML/CSS/JS frontend.
    -   Features a dynamic download configuration form.
    -   **Integrated Library:** A modal interface to browse and launch previously downloaded books.
    -   **Integrated Web Player:** A custom audio player supporting `M4B`/`MP4` (with chapter markers on the timeline) and `ZIP` archives (acting as a dynamic playlist). It includes smart `localStorage` bookmarks that save the playback position and current track.

-   **`recover_metadata.py` (Utility):**
    -   A standalone script to retroactively extract chapter metadata from older `.m4b` files using `ffprobe` and generate the required `.json` files, making legacy downloads compatible with the new web player.

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

The codebase has recently undergone a major feature expansion and refactoring phase aimed at transforming it from a simple downloader into a complete audiobook library and playback suite.

### Recent Feature Highlights:
*   **Integrated Web Player:** Added a comprehensive streaming player capable of playing single files (MP3/M4B) with chapter navigation, and seamlessly streaming extracted ZIP archives as sequential playlists.
*   **Smart Bookmarking:** The frontend now automatically saves playback position and playlist track index to `localStorage`, allowing users to resume books exactly where they left off.
*   **Library Management:** An API and UI modal to browse all local downloads without needing to re-fetch them.
*   **Dynamic Settings:** Users can now select their desired download directory using a native system dialog (`tkinter`), persisting the choice in a `settings.json` file.
*   **Async Event Loop Optimization:** Migrated heavy file writes (like `index.html` serving and direct URL downloads) to `aiofiles`. Replaced the deprecated FastAPI `@app.on_event("startup")` with the modern `@asynccontextmanager lifespan`.
*   **yt-dlp API Integration:** Moved away from launching `yt-dlp` as an external subprocess and parsing its `stdout` via Regex. It now utilizes the `yt_dlp.YoutubeDL` Python API, wrapped in a thread executor with a debounced `progress_hook` for precise UI updates.

### Areas for Future Improvement / Technical Debt:
1.  **Playwright Persistence:** Currently, the fallback scraper (`async with async_playwright()`) spins up a new Chromium context for *every* failed `httpx` request. While this prevents memory leaks, it adds significant overhead (seconds) to the initial scraping phase. A future improvement could involve managing a persistent browser context pool within the FastAPI `lifespan`.
2.  **State Management (`progress_store`):** The application state (download progress) is stored in a standard Python dictionary. This works perfectly for a single-worker deployment (`python main.py`), but will break if deployed using Gunicorn/Uvicorn with multiple workers (`--workers 4`), as memory won't be shared. Moving this to a lightweight Redis or Memcached instance would make the app horizontally scalable.

---
*Document updated on 16 March 2026.*