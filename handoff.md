# 🏗️ SonicBook Architecture & Handoff

This document provides a comprehensive overview of the **SonicBook** project architecture, current state of the codebase, setup requirements, and details about recent refactorings. It serves as a guide for future development and maintenance.

## 1. System Architecture Overview

SonicBook is an asynchronous web application built on **FastAPI**. Its primary goal is to scrape audiobook metadata (titles, chapters, stream URLs), download fragmented audio streams (HLS/m3u8) concurrently at high speed, and provide an integrated playback experience.

### Core Components

-   **`main.py` (The Entry Point):**
    -   Serves the FastAPI web application.
    -   Manages API endpoints:
        -   `/api/info`: Fetches book metadata.
        -   `/api/download`: Starts a background download task.
        -   `/api/progress/{task_id}`: Polls download/assembly progress.
        -   `/api/files/{file_name:path}`: Streams audio files (supports `Range` requests and subdirectories for ZIPs).
        -   `/api/library`: Lists all local downloads.
        -   `/api/metadata/{file_name}`: Fetches chapter metadata JSON (and extracts ZIPs on-the-fly for playback).
        -   `/api/settings/choose_folder`: Opens a native folder selection dialog.
    -   Maintains an in-memory `progress_store`.
    -   Runs a background `cleanup_task` within the FastAPI `lifespan`.

-   **`scraper.py` (Metadata Extraction):**
    -   Uses `httpx[http2]` + `BeautifulSoup4` for high-speed parsing.
    -   Falls back to **Playwright (Chromium)** for JS-heavy sites.

-   **`processor.py` (The Heavy Lifter):**
    -   Handles downloading via `yt_dlp` Python API in a separate thread.
    -   Provides real-time, throttled progress updates to the frontend.
    -   Assembles final files (`.m4b`, `.mp3`, or `.zip`) using FFmpeg.
    -   Generates a sidecar `.json` metadata file for each book to enable player navigation.

-   **`config.py` (Configuration):**
    -   Dynamic paths loaded from `settings.json`.
    -   System-level FFmpeg/FFprobe path management.

-   **`index.html` (Frontend):**
    -   **Symmetric Sliding Panels:** A unique 3-panel layout.
        -   **Left Panel:** Sliding Library to browse and launch books.
        -   **Center Card:** Main download interface and playback controls.
        -   **Right Panel:** Sliding Table of Contents (Chapters).
    -   **Interactive Player:** Custom UI with:
        -   Timeline with chapter markers.
        -   **Visual Chapter Progress:** Background fills in the side panel showing elapsed time within each chapter.
        -   **Dynamic Timers:** Shows current position vs. total length for the active chapter.
        -   **Interactive Seeking:** Jump to any position in a chapter by clicking its item in the side panel.
    -   **Smart Bookmarking:** Saves `currentTime` and `trackIndex` (for ZIPs) to `localStorage`.
    -   **Full i18n:** Supports English and Russian with dynamic UI updates.
    -   **Theming:** Dark and Light mode support.

-   **`recover_metadata.py` (Utility):**
    -   Retroactively generates JSON metadata for legacy M4B files.

---

## 2. System Requirements & Setup

1.  **Python 3.10+**
2.  **FFmpeg & FFprobe**: Must be in PATH or defined in `config.py`.
3.  **Playwright Browsers**: `playwright install chromium`

---

## 3. Current State of the Codebase

SonicBook has evolved from a simple downloader into a comprehensive self-hosted audiobook library and playback system.

### Recent Feature Highlights:
*   **Three-Panel Architecture:** Symmetric sliding panels for Library and Chapters that dynamically expand the app container.
*   **Advanced ZIP Support:** "On-the-fly" extraction and sequential playlist streaming for ZIP archives.
*   **Granular Progress Tracking:** Visual background fills and dynamic timers per chapter in the side panel.
*   **Native Folder Selection:** Integrates `tkinter` to bypass browser security limits for local path selection.
*   **Performance:** Fully asynchronous I/O and optimized `yt-dlp` API integration.

### Areas for Future Improvement / Technical Debt:
1.  **Playwright Persistence:** Managing a browser context pool.
2.  **State Management:** Redis for multi-worker scaling.
3.  **UI Feedback:** More granular error reporting for failed scrapers.

---
*Document updated on 16 March 2026.*