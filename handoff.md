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
    -   **Multi-layout support:** Optimized to handle various `akniga.org` page templates (standard and legacy).
    -   Falls back to **Playwright (Chromium)** for JS-heavy sites or when direct parsing fails.

-   **`processor.py` (The Heavy Lifter):**
    -   Handles downloading via `yt_dlp` Python API in a separate thread.
    -   Provides real-time, throttled progress updates to the frontend.
    -   Assembles final files (`.m4b`, `.mp3`, or `.zip`) using FFmpeg.
    -   **Validation:** Ensures metadata integrity (e.g., non-zero chapter durations) to prevent FFmpeg assembly failures.
    -   Generates a sidecar `.json` metadata file for each book to enable player navigation.

-   **`config.py` (Configuration):**
    -   Dynamic paths loaded from `settings.json`.
    -   System-level FFmpeg/FFprobe path management.

-   **`index.html` (Frontend):**
    -   **Symmetric Sliding Panels:** A unique 3-panel layout.
        -   **Left Panel:** Sliding Library to browse and launch books. Handles play/pause toggling and per-book progress visualization.
        -   **Center Card:** Main download interface and playback controls.
        -   **Right Panel:** Sliding Table of Contents (Chapters).
    -   **Interactive Player:** Custom UI with:
        -   Timeline with bright, accurate chapter markers (rendered post-load).
        -   **Visual Chapter Progress:** Background fills in the side panel showing elapsed time within each chapter.
        -   **Dynamic Timers:** Shows current position vs. total length for the active chapter.
        -   **Interactive Seeking:** Jump to any position in a chapter by clicking its item in the side panel.
    -   **Smart Bookmarking & Persistence:** 
        -   Saves `currentTime`, `duration`, and `trackIndex` (for ZIPs) to `localStorage`.
        -   Persists UI state (open panels, current mode, last played book) across page reloads.
    -   **Full i18n & Theming:** Reliable English and Russian support with dynamic UI updates and Dark/Light mode.

-   **`recover_metadata.py` (Utility):**
    -   Retroactively generates or "repairs" JSON metadata for legacy or incomplete downloads using `ffprobe`.

---

## 2. System Requirements & Setup

1.  **Python 3.10+**
2.  **FFmpeg & FFprobe**: Must be in PATH or defined in `config.py`.
3.  **Playwright Browsers**: `playwright install chromium`

---

## 3. Current State of the Codebase

SonicBook is now a robust, feature-complete audiobook management system.

### Recent Feature Highlights:
*   **Fully Persistent UI:** Page reloads no longer interrupt the experience; panels and player state are remembered.
*   **Interactive Side Panels:** Clickable headers, smooth drawer animations, and real-time synchronization between the library list and the main player.
*   **Robust Scraping:** Improved reliability for diverse source layouts and a retroactive metadata recovery tool.
*   **Polished UX:** Custom indigo scrollbars, white timeline markers, and comprehensive Russian localization.

### Areas for Future Improvement / Technical Debt:
1.  **Playwright Persistence:** Managing a browser context pool within `lifespan`.
2.  **State Management:** Redis for multi-worker scaling.
3.  **Error Feedback:** More detailed error states in the UI for scraper or download failures.

---
*Document updated on 17 March 2026.*