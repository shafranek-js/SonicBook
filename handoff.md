# 🏗️ SonicBook Architecture & Handoff

This document provides a comprehensive overview of the **SonicBook** project architecture, current state of the codebase, setup requirements, and details about recent refactorings. It serves as a guide for future development and maintenance.

## 1. System Architecture Overview

SonicBook is an asynchronous web application built on **FastAPI**. Its primary goal is to scrape audiobook metadata (titles, chapters, stream URLs), download fragmented audio streams (HLS/m3u8) concurrently at high speed, and provide an integrated playback experience.

### Core Components

-   **`main.py` (Application Composition):**
    -   Serves the static shell and composes the FastAPI application.
    -   Registers route modules from `routes/`.
    -   Owns lifecycle startup/shutdown wiring, including Playwright initialization and progress-store flushing.
    -   Keeps API/business logic out of the entrypoint wherever practical.

-   **`scraper.py` (Metadata Extraction):**
    -   Uses `httpx[http2]` + `BeautifulSoup4` for high-speed parsing.
    -   **Multi-layout support:** Optimized to handle various `akniga.org` page templates (standard and legacy).
    -   Falls back to **Playwright (Chromium)** for JS-heavy sites, incorporating an independent self-healing context pool to recover gracefully from browser crashes or external process termination.

-   **`media_helpers.py` (Shared Media Helpers):**
    -   Provides filename sanitization and cover-extension inference shared by scraping and processing code without coupling those layers to each other.

-   **`ffmpeg_helpers.py` (FFmpeg Helpers):**
    -   Provides FFprobe duration reads, FFmpeg progress parsing, and bounded FFmpeg execution helpers used by the processing pipeline.

-   **`download_sources.py` (Download Sources):**
    -   Provides source acquisition for direct MP3 URL lists, direct ZIP URLs, and yt-dlp/HLS sources, returning staged source files for the processor assembly pipeline.
    -   Large direct single-file sources can use controlled multi-range downloading after a `Range: bytes=0-0` probe proves partial-content support; failures fall back to single-stream downloading.

-   **`media_assembly.py` (Media Assembly):**
    -   Provides M4B chapter assembly and ZIP chapter splitting, while `processor.py` keeps compatibility wrappers for existing tests and call sites.

-   **`media_assets.py` (Media Assets):**
    -   Downloads and stages cover art for completed local library artifacts.

-   **`library_storage.py` (Library Storage):**
    -   Provides task work-directory preparation and completed-artifact moves into the configured local library.

-   **`library_finalization.py` (Library Finalization):**
    -   Provides completed ZIP validation and JSON sidecar generation/move logic for local library artifacts.

-   **`processor.py` (The Heavy Lifter):**
    -   Orchestrates the media pipeline after source acquisition.
    -   Handles source acquisition via helpers for yt-dlp/HLS, direct MP3 URL lists, and direct ZIP downloads.
    -   Provides real-time, throttled progress updates to the frontend.
    -   Assembles final files (`.m4b`, `.mp3`, or `.zip`) using FFmpeg.
    -   Generates a sidecar `.json` metadata file for each book to enable player navigation.

-   **`config.py` (Configuration):**
    -   Dynamic paths loaded from `settings.json`.
    -   System-level FFmpeg/FFprobe path management.
    -   Concurrency settings for sub-processes.
    -   Root-level `.env` support for local overrides.
    -   Bounded environment parsing for download tuning and media tool paths, with warnings and safe defaults for invalid local values.

-   **`google_drive_service.py` (Google Drive Integration):**
    -   Handles Google OAuth token exchange and callback status.
    -   Accepts raw Drive folder IDs and shared Google Drive folder links.
    -   Lists supported audiobooks from configured folders with short-lived snapshot caching and explicit refresh support.
    -   Imports selected Drive books into the local library.
    -   Proxy-streams media through `Range`-aware backend endpoints for remote playback without importing.

-   **`bookmark_service.py` (Persistence & State Tracking):**
    -   Synchronizes playback metadata, last active sessions, and `duration` checkpoints.
    -   Operates a rapid In-Memory dictionary cache (`_state_cache`), preventing blocking disk operations on every partial SSE frame update during media playback.

-   **`index.html` + `static/app.js` + `static/style.css` (Frontend):**
    -   **Symmetric Sliding Panels:** A dynamic 3-panel layout.
    -   **Interactive Player:** Media Session integrations, interactive seeking, variable playback rates, and keyboard shortcuts.
    -   **Sleep Timer:** Toolbar countdown timer implemented in `static/player-ui.js`; resets on activity, pauses playback after inactivity, auto-resumes when activity returns after a timer-triggered pause, coordinates screen dimming, and fades audio to zero during the final 60 seconds.
    -   **Adaptive Cover Sizing:** Blur-backed frames ensuring tall covers never cause vertical UI overflow.
    -   **Settings:** Language, local library folder, sync profile, Google Drive connection/folder, and app-data reset.
    -   **Frontend Contracts:** Core Vanilla JS state objects now have lightweight JSDoc typedefs for editor support without introducing TypeScript or npm build tooling.

-   **System UX Endpoints (`routes/system_routes.py`):**
    -   `/api/system/idle` reads Windows system idle time for sleep-timer reset behavior beyond browser-only activity events.
    -   `/api/system/brightness` provides best-effort brightness control for sleep-timer dimming through Windows WMI/CIM, with frontend fallback to an in-window black overlay when display control is unsupported.

-   **Bookmark Routes (`routes/bookmark_routes.py`):**
    -   Owns `/api/bookmarks/*` and `/api/playback/active`, delegating persistence and cross-client playback state to `bookmark_service.py`.

-   **Progress Routes (`routes/progress_routes.py`):**
    -   Owns `/api/progress/*`, including task polling and SSE streaming, while `progress_service.py` remains the persisted progress state store.

-   **Settings Routes (`routes/settings_routes.py`):**
    -   Owns `/api/settings/*`, including local library folder selection and playback profile storage status.

-   **Library Routes (`routes/library_routes.py`):**
    -   Owns `/api/library`, `/api/files/*`, and `/api/metadata/*`, including local path validation, `Range` streaming, and ZIP metadata responses.

-   **Google Drive Routes (`routes/google_drive_routes.py`):**
    -   Owns `/api/google-drive/*`, including OAuth callback HTML responses, Drive library listing/import, metadata building, stream probing, and `Range` proxy streaming.

-   **Download Routes (`routes/download_routes.py`):**
    -   Owns `/api/info`, `/api/download`, URL validation, duplicate active-task reuse, and background download orchestration into `processor.run_fast_download()`.

-   **Source-Specific Scraping:**
    -   `scraper.py` supports direct metadata extraction, Playwright fallback, and Audioboo ZIP discovery through `DIRECT_ZIP:`.
    -   Audioboo pages usually do not provide timed chapters; ZIP playback relies on playlist generation from files inside the archive.

-   **`recover_metadata.py` & `backfill_covers.py` (Utilities):**
    -   Retroactively repair collections locally, strictly relying on asynchronous disk writes (`aiofiles`) to maintain high ingestion speeds without starving the OS.

---

## 2. System Requirements & Setup

1.  **Python 3.10+** (Recommend 3.11 for improved async stack performance).
2.  **FFmpeg & FFprobe**: Must be in PATH or exposed via `FFMPEG_PATH` / `FFPROBE_PATH`.
3.  **Playwright Browsers**: Run `playwright install chromium` prior to usage.
4.  **Google Drive API** (optional): Setup OAuth strings via `.env` for private Drive folders. Public/shared folders can often be browsed by saving a shared folder link without OAuth.

---

## 3. Current State of the Codebase

SonicBook is currently in a hyper-optimized and heavily fortified state following a comprehensive architectural and stability sprint (April 2026).

### Recent Backend Stability & Architecture Highlights:
*   **Asynchronous I/O Nirvana:** Transitioned entirely from synchronous Python `open()` calls to `aiofiles` and `asyncio.to_thread`. Drive streams, chunked uploads, and massive 1GB+ fragmented M3U8 downloads no longer stall FastAPI.
*   **Playwright Resurrection:** Scraper initialization is now fault-tolerant. Chromium instances natively heal themselves and attempt transparent reloads should the underlying browser process be killed externally.
*   **Threaded Process Isolation:** `Tkinter` (used for selecting paths in the UI) was famously deadlocking the Python ThreadPool due to Apple/Windows GUI thread violations. The folder dialogs have been entirely decoupled into an external `subprocess`, resolving all UI freezing.
*   **Rapid Bookmark Caching:** Massive reduction in hardware I/O latency; bookmark writes dynamically cache into memory upon parsing and flush to filesystem lazily, accommodating multi-tab high-traffic frontend synchronizations seamlessly.
*   **Tackled ZipSlip:** Ensured all extracted archive paths strictly adhere to bounded resolution rules, neutralizing Zip Slip directory traversal vulnerabilities.
*   **Extensive Test Suite Coverage:** Wove a dense net of `IsolatedAsyncioTestCase` units over processing logic, download headers, archive isolation schemas, and bookmark migrations. 
*   **Bedtime Listening UX:** Sleep timer now combines activity reset, auto-pause, auto-resume, display dimming, and final-minute audio fade-out without changing the user's long-term volume setting.
*   **Frontend Regression Guardrails:** Python Playwright E2E smoke coverage starts a temporary uvicorn server and verifies the app shell, Settings opacity/content, sleep timer controls, minimum-brightness persistence, and Local/Drive switching without real Google credentials or a real audiobook library.
*   **Safer Local Configuration:** Environment overrides for FFmpeg paths and download concurrency now use explicit parsing helpers, clamp bounded values, and fall back to defaults instead of crashing on malformed `.env` values.

### Areas for Future Improvement / Technical Debt:
1.  **Live Drive Validation:** E2E live Drive integration rests primarily on staging; live QA validation is deferred to real credential injection mapping runs. 
2.  **WebSockets:** Although SSE functions flawlessly, shifting progress endpoints and dynamic client connections (Drive notifications) to Native WebSockets presents a natural evolutionary path for the architecture.
3.  **Advanced Chapter Detection:** FFprobe heuristics currently rely on well-defined embedded markers. Exploring Deep-Learning VAD (Voice Activity Detection) integrations for auto-splitting trackless monolith audio files could heavily bolster the application's unique value offering.

---
*Document updated on 6 May 2026.*
