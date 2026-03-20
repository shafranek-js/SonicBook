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
- [x] 2. **Book Covers:**
  - Update `scraper.py` to extract the high-resolution cover image URL.
  - Update `processor.py` to download and save the cover as `[book_name].jpg`.
  - Update the UI to display the cover image cleanly below or alongside the central player.
- [x] 3. **Keyboard Shortcuts:** Add global hotkeys (Space for Play/Pause, Left/Right arrows for 15s seek).
- [x] 4. **Media Session API:** Integrate `navigator.mediaSession` to allow users to control playback from their OS media widget, lock screen, or physical media keys, complete with metadata (title, artist, cover art).
- [x] 1. **Async ZIP Extraction:** Fix event loop blocking in `main.py` by moving `zipfile.extractall` to a separate thread executor.
- [x] 2. **Race Condition Protection:** Add `asyncio.Lock` for ZIP extraction to prevent filesystem corruption on concurrent requests.
- [x] 3. **Frontend Componentization:** Extract CSS and JS from `index.html` into `static/style.css` and `static/app.js` for better maintainability and caching.
- [x] 4. **Playwright Optimization:** Initialize a single persistent browser context in FastAPI `lifespan` instead of launching a new one per request.
- [x] 5. **Subprocess Timeouts:** Add strict `asyncio.wait_for` timeouts to `yt-dlp` and `ffmpeg` execution to prevent memory/process leaks on network hangs.
- [x] 6. **Modernize Progress Delivery:** Replace polling (`setInterval`) with Server-Sent Events (SSE) or WebSockets for real-time progress updates without DDoS-ing the server.
- [x] 8. **Library Chapter Auto-Open:** Automatically open the right-side chapters panel when a user selects a library item that has chapter metadata.
- [x] 9. **Compact Center Panel Layout:** Remove redundant hero text, move the save-path control into the toolbar, and normalize spacing in the middle panel.
- [x] 10. **Adaptive Player Cover Layout:** Let the player cover grow to full width while dynamically constraining height so the center panel stays fully visible without a vertical scrollbar.
- [x] 11. **Retroactive Cover Backfill:** Add a standalone `backfill_covers.py` utility plus `cover_aliases.json` overrides to populate missing artwork for older library items.
- [x] 12. **Unified Progress Fill Styling:** Use the same primary-color translucent progress fill treatment in both the library list and the chapter panel.
- [x] 13. **Blur-Backed Cover Frame:** Fill unused side space around tall cover art with a blurred copy of the same image behind the main player cover.
- [x] 14. **Standardize Player Controls:** Replace emoji transport buttons with standard media-style controls and align the chapters button with the same visual language.

## Code Review Findings

### P1 - Critical
- [x] **Escape untrusted chapter titles in `static/app.js`:**
  Stop interpolating remote chapter and playlist titles directly into `innerHTML` so untrusted book pages cannot inject script into the UI.
- [x] **Fix `knigavuhe.org` tuple contract in `scraper.py`:**
  Return exactly 4 values from `get_book_info()` in the direct-URL branch so `/api/info` and `/api/download` stop crashing on unpack.
- [x] **Fix uninitialized `total_frags` in `processor.py`:**
  Ensure the `DIRECT_URLS:` path initializes and reports assembly progress without raising `UnboundLocalError`.
- [x] **Close absolute-path escape in file endpoints:**
  Harden `/api/files` and `/api/metadata` path handling in `main.py` so Windows drive-letter and UNC paths cannot escape `DOWNLOADS_DIR`.
- [x] **Fix chapter duration parsing in `scraper.py`:**
  Replace the broken `value.split(':')` reference with the real `time_str` input so BS4 chapter timing works again.

### P2 - High
- [x] **Convert unexpected `process_book()` failures into terminal error states:**
  Add a top-level exception guard in `main.py` so crashed background tasks do not leave permanent non-terminal `progress_store` entries behind.
- [x] **Merge sidecar metadata into ZIP playback responses:**
  Reuse the generated JSON metadata in `main.py` for ZIP books so title and cover art are available in the player.
- [x] **Avoid mutating `DOWNLOADS_DIR` before settings save succeeds:**
  Update `config.py` so folder changes only affect runtime state after directory creation and `settings.json` persistence succeed.
- [x] **Refresh `progress_store` timestamps during active downloads:**
  Update task timestamps on progress writes so long downloads are not evicted by `cleanup_task()` before completion.
- [x] **Implement real async ZIP extraction with locking:**
  Move `zipfile.extractall()` off the event loop and actually use `zip_extraction_locks` in `main.py`.
- [x] **Remove hardcoded FFmpeg paths from `config.py`:**
  Default to `ffmpeg` and `ffprobe` or another portable configuration instead of machine-specific local paths.
- [x] **Repair `requirements.txt` encoding/content:**
  Remove the corrupted `aiofiles` line with embedded NUL characters so clean installs work reliably.

## Current Status

- [x] **No open TODO items remain in this file.**

## Refactor Plan

- [x] 1. **Library Event Delegation (`static/app.js`):**
  Replace inline `onclick` handlers in library row markup with `data-*` attributes plus a single delegated click handler on `#libraryList`.
- [x] 2. **Frontend State Object (`static/app.js`):**
  Consolidate `step`, language/mode, return-to-player flow, and related UI flags into one explicit state object instead of scattered globals and DOM-driven state.
- [x] 3. **Frontend Module Split (`static/app.js`):**
  Split the current monolith into separate files for app shell, library, player, download flow, and layout/responsive behavior.
  Completed: app shell remains in `static/app.js`; library UI extracted to `static/library-ui.js`; download flow extracted to `static/download-flow.js`; layout and panel resizing extracted to `static/layout-ui.js`; player logic extracted to `static/player-ui.js`.
- [x] 4. **Backend Service Extraction (`main.py`):**
  Move library probing, progress-store logic, and ZIP playback helpers into separate service modules so `main.py` is mostly routing and lifecycle glue.
  Completed: library probing and sidecar metadata loading extracted to `library_service.py`; progress store extracted to `progress_service.py`; ZIP playback and extraction helpers extracted to `zip_service.py`.
- [x] 5. **Stylesheet Partitioning (`static/style.css`):**
  Split CSS into base/tokens, layout, library, player, and responsive layers to reduce cascade-sensitive changes.
  Completed: base/tokens extracted to `static/styles/base.css`; shell/layout extracted to `static/styles/layout.css`; player rules extracted to `static/styles/player.css`; library/panel rules extracted to `static/styles/library.css`; responsive rules extracted to `static/styles/responsive.css`; `static/style.css` now acts as the aggregator plus shared center-state styles.

## Follow-up Refactors

- [x] 6. **Centralize UI State Rendering (`static/app.js`, `static/download-flow.js`):**
  Make `updateUI()` the main source of truth for center-panel visibility so `step` is not split across direct `style.display` mutations in the download and player-return flows.
- [x] 7. **Chapter Panel Event Delegation (`static/player-ui.js`):**
  Replace inline `onclick` handlers in the player chapter list with `data-*` attributes plus a single delegated click handler on `#playerChaptersList`.

## Progress UX

- [x] 8. **Split Download Progress Into Distinct Stages:**
  Replace the old 0-95 download scale with explicit `Downloading` and `Assembling` phases so the UI no longer jumps from ~94% straight into a wait state.
- [x] 9. **Report Real Assembly Progress Where Available:**
  Emit honest assembly progress for ZIP chapter splitting and M4B creation instead of a fake instant jump to 100%.

## Remaining Frontend State Cleanup

- [x] 10. **Render Status/Idle/Toolbar Strictly From `appState`:**
  Move status visibility/text/tone and main toolbar action rendering fully behind `updateUI()` so flow functions mutate state only and no longer write those DOM branches directly.

## Download Staging

- [x] 11. **Stage Downloads Locally Before Library Move:**
  Download fragments, `.part/.ytdl`, concat lists, and intermediate audio files into a local app-owned work directory instead of writing them directly into the user library path.
- [x] 12. **Move Only Completed Artifacts Into Library:**
  After successful assembly, move the final audio/zip file plus sidecar JSON and cover image from local staging into `DOWNLOADS_DIR`.

## Direct URL Reliability

- [x] 13. **Stabilize `knigavuhe` Direct URL Downloads:**
  Replace the hanging streamed direct-URL path with a simpler bounded-concurrency downloader that validates non-empty MP3 files before merge.
- [x] 14. **Fix direct MP3 -> M4B assembly and reject empty artifacts:**
  Transcode direct MP3 sources to an M4B-compatible audio codec during assembly and refuse to move zero-byte output files into the library after failed `ffmpeg` runs.
- [x] 15. **Implement resumable direct MP3 downloads for unstable sources:**
  Add `Range`-based resume support for direct MP3 URLs so interrupted `knigavuhe` chapter downloads can continue from existing partial files instead of restarting from zero.
  Implemented:
  - Byte-range resume for existing partial chapter files.
  - Safe fallback to full restart when the server ignores or rejects `Range`.
  - Validation against expected final response size before accepting a resumed file.
  - Reduced direct-download concurrency and stronger retry backoff.
  Remaining follow-up:
  - None in this area; duplicate same-book launches are now guarded at the task-creation layer.
  Plan:
  - Probe direct MP3 URLs for partial-content support via `Range`/`206` behavior.
  - Resume from existing partial file size when the server honors byte ranges.
  - Fall back to full restart when the server ignores `Range` or returns invalid offsets.
  - Validate final file size against expected response length before accepting the chunk.
  - Reduce `knigavuhe` concurrency and add stronger backoff around resumed retries.
  - Guard against duplicate same-book launches so task folders and logs do not interleave.

## Task Coordination

- [x] 17. **Prevent duplicate same-book background downloads:**
  Reuse the existing active `task_id` for the same source URL instead of launching a second concurrent job that would interleave logs and staging folders.

## Playback Continuity

- [x] 16. **Preserve playback across mode switches and completed downloads:**
  Do not pause the current book when switching from player mode into download mode with `preservePlayer`, and do not auto-interrupt current playback when a newly downloaded book finishes assembling unless there was no active book already loaded.

## Google Drive Integration

- [x] 18. **Persist Google Drive settings and connection state:**
  Extend `settings.json` handling so SonicBook can safely store Drive-specific settings such as `folder_id`, token metadata, and connection status without regressing the existing downloads-folder flow.
- [x] 19. **Add Google Drive OAuth backend scaffolding:**
  Create a dedicated backend service for Google OAuth URL generation, callback handling, token refresh, and connection-status reporting using Google Drive API configuration from environment variables.
- [x] 20. **Expose Google Drive settings/auth endpoints in FastAPI:**
  Add API endpoints for Drive status, connect URL, callback, disconnect, and folder ID persistence so the frontend can attach later without backend rewiring.
- [x] 21. **List audiobook files from a configured Drive folder:**
  Implement a Drive library adapter that enumerates supported audiobook files plus sidecar cover/metadata files from a target `folderId`.
- [x] 22. **Import selected Drive files into the local SonicBook library:**
  Download a chosen Drive audiobook and its sidecars into local staging, then move the completed artifacts into `DOWNLOADS_DIR`.
- [x] 23. **Add Settings UI for Google Drive connection:**
  Extend the Settings popover with connection state, connect/disconnect controls, and a configurable `folderId`.
- [x] 24. **Add Google Drive library browsing in the UI:**
  Surface Drive-backed library items cleanly without breaking the existing local-library-first workflow.
- [x] 25. **Support streamed playback from Google Drive via backend proxy:**
  Add `Range`-aware proxy streaming for Drive-hosted audio so remote books can be played without importing first.
- [x] 26. **Show visible Drive import activity in the library UI:**
  Make `Import` show immediate in-row feedback (`Importing...` and short success state) so long Drive copies do not look like a stuck UI.
- [x] 27. **Show bookmark-based progress for streamed Drive books:**
  Reuse `bookmark_drive_*` playback data to render active-state and progress fill in the Drive library just like local books.
- [x] 32. **Keep imported Drive books permanently marked as imported:**
  Derive the Drive-row `Imported` state from the actual presence of the book in the local library so the green imported status survives reloads and is not just a temporary button flash.

## Cross-Device Bookmark Sync

- [x] 28. **Add a persistent backend bookmark store:**
  Move playback progress into a JSON-backed server store keyed by a shared `book_id` instead of keeping progress only in per-browser `localStorage`.
- [x] 29. **Expose bookmark read/write/delete API endpoints:**
  Add backend endpoints for bookmark summary lookup plus per-book save/delete so all clients of the same SonicBook instance can see the same progress.
- [x] 30. **Sync player progress to the backend with local fallback:**
  Load saved position from the backend when a book opens, keep legacy `localStorage` as fallback, and push throttled updates back to the server during playback.
- [x] 31. **Render shared bookmark progress in both Local and Drive libraries:**
  Use backend bookmark summary to paint progress/completed state for both local files and Drive streams, and make reset clear the shared bookmark too.
- [x] 33. **Make `book_id` collision-resistant with backward-compatible bookmark fallback:**
  Replace the fragile basename-only identity with a size-aware `book_id`, while preserving reads and deletes of older bookmark keys so existing progress is not lost.
- [x] 34. **Stop Drive imported-state from loading the full local library:**
  Add a lightweight backend endpoint that returns only imported local `book_id`s and use it in the Drive library instead of calling the heavier `/api/library` endpoint on every refresh.

## Library Performance

- [x] 35. **Add a persistent library index for cached metadata:**
  Store per-book library metadata in a JSON index and invalidate entries by file size, audio mtime, and sidecar mtime so unchanged books do not trigger repeated `ffprobe` and sidecar parsing on every load.
- [x] 36. **Reuse the library index for lightweight imported-book lookups:**
  Make imported-state queries reuse the same indexed snapshot instead of re-scanning and re-probing the full library separately.
- [x] 37. **Add short-lived Drive library snapshot caching:**
  Cache Google Drive folder listings on the backend for a short TTL so repeated Drive opens do not always wait on a live Google API round-trip.
- [x] 38. **Add explicit Drive refresh control in the library header:**
  Keep normal Drive browsing fast via cached snapshots, but expose a manual refresh action so the user can force a live reload whenever needed.
