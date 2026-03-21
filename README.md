# 🚀 SonicBook

**SonicBook** is a high-speed audiobook downloader designed specifically for audiobook streaming sites. It combines extreme download speeds with smart chapter splitting, making it the ultimate tool for audiobook enthusiasts.

## ✨ Features

-   **Extreme Speed:** Downloads book fragments in **16 concurrent streams**.
-   **Integrated Web Player:** Stream your books directly in the browser with **M4B chapter support**, **ZIP playlist sequential playback**, **keyboard shortcuts**, and **Media Session** integration.
-   **Refined Player Controls:** The built-in player uses standard media-style transport controls and a visually unified chapter button instead of emoji-driven buttons.
-   **Visual Playback Progress:** Watch your progress in real-time with matching indigo background fills in both the chapter panel and the library list, plus dynamic chapter timers.
-   **Smart Library:** Manage and browse all your downloads in a sleek sliding side panel. Selecting a book restores playback and auto-opens the chapter panel when metadata is available.
-   **Smart Bookmarks:** Automatically saves your playback position and current track to pick up exactly where you left off.
-   **Native Directory Choice:** Select any folder on your computer to save books using a native system dialog.
-   **Smart Chapter Splitting:** Automatically provides **M4B with embedded chapters** or a **ZIP archive** with correctly named files.
-   **Cover Art Pipeline:** Extracts, downloads, stores, retroactively backfills, and displays local book covers in the built-in player.
-   **Adaptive Cover Layout:** Player covers expand to the full player width, automatically shrink just enough to avoid vertical scrolling in the center panel, and fill side gaps with a blurred copy of the same artwork behind the main image.
-   **Modern UI:** A compact 3-panel sliding interface with Dark/Light mode and full **EN/RU localization**.
-   **No Quality Loss:** Downloads original AAC/MP4/MP3 streams directly.

## 🛠️ Requirements

To run SonicBook correctly, you need the following system components and libraries:

1.  **Python 3.10+**: The core language for the backend.
2.  **FFmpeg**: Essential for parsing streams, splitting chapters, and converting audio. **Must be installed and either added to your System PATH or provided via `FFMPEG_PATH` / `FFPROBE_PATH` environment variables**.
    *   *Windows*: Can be installed via Winget (`winget install -e --id Gyan.FFmpeg`).
    *   *macOS*: `brew install ffmpeg`
    *   *Linux*: `sudo apt install ffmpeg`
3.  **Playwright (Chromium)**: A headless browser engine used for advanced scraping when direct HTML parsing fails.
4.  **HTTP Client (`httpx`)**: Used for scraping, Drive access, and direct media downloads. SonicBook works with the pinned `httpx` dependency from `requirements.txt`; no separate extra install step is required.
5.  **Aiofiles**: Used for efficient, non-blocking disk operations during downloads.

## 🚀 Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/shafranek-js/SonicBook.git
    cd SonicBook
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright browser:**
    ```bash
    playwright install chromium
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

5.  If FFmpeg is not in PATH, set `FFMPEG_PATH` and `FFPROBE_PATH` before launch.

    You can also place overrides into a local `.env` file in the project root. See [`.env.example`](/C:/Projects/SonicBook/.env.example).

6.  Open your browser and navigate to `http://localhost:8000`.

### Smoke Test

To confirm that SonicBook starts correctly on Windows and the core endpoints respond:

```powershell
./smoke_test.ps1
```

This script checks:
- app startup
- `/`
- `/api/settings/folder`
- `/api/google-drive/status`

### Automated Checks

The repository now includes a minimal GitHub Actions pipeline in
[`/.github/workflows/ci.yml`](/C:/Projects/SonicBook/.github/workflows/ci.yml)
that runs:

- `pytest` on Linux
- `smoke_test.ps1` on Windows, including Playwright Chromium and FFmpeg setup

Runtime note:
- `httpx` is installed with the `http2` extra because the scraper and some remote fetch paths explicitly enable HTTP/2 clients.

## ☁️ Google Drive

SonicBook can now connect to Google Drive without requiring the desktop Google Drive sync app.

What already works:
-   Connect a Google account through OAuth
-   Save a Drive `folderId` in `Settings`
-   Browse audiobook files from that Drive folder in the left library panel
-   Import a selected Drive book into the local SonicBook library
-   Stream supported remote audio files through the backend proxy

### Configuration

1.  Copy [`.env.example`](/C:/Projects/SonicBook/.env.example) to `.env`
2.  Fill in:
    -   `GOOGLE_DRIVE_CLIENT_ID`
    -   `GOOGLE_DRIVE_CLIENT_SECRET`
    -   optionally `GOOGLE_DRIVE_REDIRECT_URI`
3.  Restart SonicBook
4.  Open `Settings` and use `Connect Google Drive`

Notes:
-   The default redirect URI is `http://127.0.0.1:8000/api/google-drive/auth/callback`
-   The Google OAuth client must allow that redirect URI
-   Google Drive features stay disabled until these variables are configured

## 🔁 Cover Backfill

Existing libraries can be retrofitted with covers after download history is already on disk.

-   Run `python backfill_covers.py` to scan the current download folder and fetch missing local covers.
-   `cover_aliases.json` can pin hard matches or known `source_url` pages for books with weak or ambiguous titles.
-   The current backfill flow prefers direct source pages (for example `akniga.org`), then falls back to catalog providers and ranks candidates by real image dimensions.

## 🏗️ Architecture & Development

For a detailed breakdown of the application architecture, exact dependencies, the current state of the codebase, and technical debt, please refer to the [Handoff Document](handoff.md).

## 📜 License

MIT License. Free for personal use.

---
Developed by [shafranek-js](https://github.com/shafranek-js)
