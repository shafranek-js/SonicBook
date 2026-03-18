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
4.  **HTTP/2 Support (`httpx[http2]`)**: Required for high-speed scraping of specific sites without getting blocked.
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

6.  Open your browser and navigate to `http://localhost:8000`.

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
