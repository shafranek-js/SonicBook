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
        -   `/api/progress/{task_id}`: Returns the latest persisted task snapshot.
        -   `/api/progress/stream/{task_id}`: Streams download/assembly progress over SSE.
        -   `/api/files/{file_name:path}`: Streams audio files (supports `Range` requests and subdirectories for ZIPs).
        -   `/api/library`: Lists all local downloads.
        -   `/api/metadata/{file_name}`: Fetches chapter metadata JSON (and extracts ZIPs on-the-fly for playback).
        -   `/api/settings/choose_folder`: Opens a native folder selection dialog.
    -   Maintains an in-memory `progress_store` with timestamp refresh on active writes so long-running jobs are not evicted mid-download.
    -   Runs a background `cleanup_task` within the FastAPI `lifespan`.
    -   Validates incoming book URLs and hardens file-path resolution for Windows absolute / UNC path traversal cases.

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
    -   System-level FFmpeg/FFprobe path management via PATH or `FFMPEG_PATH` / `FFPROBE_PATH`.
    -   Root-level `.env` support for local overrides, including Google Drive OAuth credentials.

-   **`google_drive_service.py` (Google Drive Integration):**
    -   Handles Google OAuth URL generation, callback exchange, token refresh, disconnect, and connection status.
    -   Lists supported audiobook files from a configured Drive folder.
    -   Imports selected Drive files into the local SonicBook library through the existing staging flow.
    -   Provides backend-proxied metadata and `Range`-aware streaming for Drive-hosted audio playback.

-   **`index.html` + `static/app.js` + `static/style.css` (Frontend):**
    -   **Symmetric Sliding Panels:** A unique 3-panel layout.
        -   **Left Panel:** Sliding Library to browse and launch books. Handles play/pause toggling, per-book progress visualization, and auto-opens the chapters panel when metadata exists.
        -   **Center Card:** Main download interface and playback controls with a compact toolbar-first layout.
        -   **Right Panel:** Sliding Table of Contents (Chapters).
    -   **Interactive Player:** Custom UI with:
        -   Timeline with bright, accurate chapter markers (rendered post-load).
        -   **Visual Chapter Progress:** Background fills in the side panel showing elapsed time within each chapter.
        -   **Dynamic Timers:** Shows current position vs. total length for the active chapter.
        -   **Interactive Seeking:** Jump to any position in a chapter by clicking its item in the side panel.
        -   **Keyboard Shortcuts:** Space toggles play/pause, Left/Right seek by 15 seconds.
        -   **Media Session Integration:** Exposes title/cover metadata and play/pause/seek handlers to OS-level media controls.
        -   **Local Cover Display:** Uses downloaded local artwork in the player when available.
        -   **Adaptive Cover Sizing:** Expands artwork to the player width, then dynamically reduces max-height only when needed to keep the center panel fully visible in the current window geometry.
        -   **Blur-Backed Cover Frame:** Uses the same image as a blurred background layer behind tall covers so side gaps are visually filled without cropping or distorting the main artwork.
        -   **Standard Media Controls:** Transport buttons now use standard media-style icons and state handling instead of emoji text toggles, and the chapter button shares the same visual language.
    -   **Smart Bookmarking & Persistence:** 
        -   Saves `currentTime`, `duration`, and `trackIndex` (for ZIPs) to `localStorage`.
        -   Persists UI state (open panels, current mode, last played book) across page reloads.
    -   **Full i18n & Theming:** Reliable English and Russian support with dynamic UI updates and Dark/Light mode.
    -   **Google Drive Settings & Library Source Toggle:**
        -   Settings now expose Google Drive connection state, connect/disconnect actions, and a configurable folder ID.
        -   The library panel can switch between `Local` and `Drive`.
        -   Drive items can be imported into the local library and, for supported formats, streamed directly through backend proxy endpoints.

-   **`recover_metadata.py` (Utility):**
    -   Retroactively generates or "repairs" JSON metadata for legacy or incomplete downloads using `ffprobe`.

-   **`backfill_covers.py` + `cover_aliases.json` (Utilities):**
    -   Retroactively downloads missing covers for existing library items.
    -   Supports manual aliases and direct `source_url` overrides for ambiguous titles.
    -   Prefers source-page artwork when known, then ranks fallback candidates by title/author match and real image dimensions.

---

## 2. System Requirements & Setup

1.  **Python 3.10+**
2.  **FFmpeg & FFprobe**: Must be in PATH or exposed via `FFMPEG_PATH` / `FFPROBE_PATH`.
3.  **Playwright Browsers**: `playwright install chromium`
4.  **Google Drive OAuth Credentials** (optional for Drive features): `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, and an allowed redirect URI such as `http://127.0.0.1:8000/api/google-drive/auth/callback`

---

## 3. Current State of the Codebase

SonicBook is now a robust, feature-complete audiobook management system.

### Recent Feature Highlights:
*   **Fully Persistent UI:** Page reloads no longer interrupt the experience; panels and player state are remembered.
*   **Interactive Side Panels:** Clickable headers, smooth drawer animations, and real-time synchronization between the library list and the main player.
*   **Automatic Chapter Panel Opening:** Selecting a book from the library now opens the right-side chapter panel automatically when metadata is available.
*   **Compact Center Layout:** The middle panel now uses a denser spacing system, toolbar-mounted save-path control, and no redundant hero text.
*   **Adaptive Player Covers:** Cover art now fills the player width, auto-constrains height to avoid center-panel scrolling, and uses a blurred backdrop layer to fill side gaps on tall artwork.
*   **Unified Progress Styling:** Library progress fills and chapter progress fills now share the same primary-color translucent treatment.
*   **Player Polish:** Keyboard shortcuts, Media Session support, local cover rendering, standard media-style controls, and automatic chapter-aware library playback are all wired into the current UI.
*   **Cover Backfill Workflow:** Existing libraries can be enriched after the fact using `backfill_covers.py` and curated `cover_aliases.json` source mappings.
*   **Google Drive Workflow:** Remote Drive folders can now be connected from the app, browsed as a second library source, imported into the local library, and streamed for supported formats.
*   **Robust Scraping:** Improved reliability for diverse source layouts and a retroactive metadata recovery tool.
*   **Polished UX:** Custom indigo scrollbars, white timeline markers, and comprehensive Russian localization.

### Areas for Future Improvement / Technical Debt:
1.  **Playwright Persistence:** Managing a browser context pool within `lifespan`.
2.  **Error Feedback:** More detailed error states in the UI for scraper or download failures.
3.  **Cover Backfill Ergonomics:** Optional in-app trigger or admin endpoint for running cover backfill without a separate script invocation.
4.  **Google Drive Validation:** Live end-to-end testing still depends on real Google OAuth credentials being configured locally; current code-level and route-level validation is complete, but real OAuth/import/stream smoke tests remain pending until credentials are supplied.

---
*Document updated on 18 March 2026.*
