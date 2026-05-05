# SonicBook

SonicBook is a local web app for downloading, organizing, and listening to audiobooks. It runs a FastAPI backend on your computer and opens a browser UI with a built-in player, local library, Google Drive library access, chapter navigation, shared playback progress, and bedtime listening tools.

## Features

- **Audiobook download workflow:** Paste or drop a supported book page URL, preview detected chapters, then download as M4B, single file, or ZIP.
- **Supported source styles:** HLS/yt-dlp sources, direct MP3 URL lists, direct ZIP downloads, and Audioboo ZIP pages.
- **Fast and safe downloads:** HLS fragment concurrency, resumable direct MP3 downloads, controlled multi-range acceleration for large direct files when the server supports `Range`, and automatic fallback to stable single-stream downloading.
- **Clear progress UI:** Download and assembly stages are shown separately through SSE updates, including real assembly progress when FFmpeg reports it.
- **Integrated player:** Browser playback for local files with M4B chapters, ZIP playlist playback, chapter panel, keyboard shortcuts, Media Session integration, cover art, and progress fills.
- **Local library:** A sliding left panel with search, grouped states (`Now Listening`, `In Queue`, `Completed`), cached metadata indexing, reset progress, and completed/not-completed controls.
- **Google Drive library:** Browse a Drive folder, stream supported remote books without importing, import books into the local library, and manually refresh cached Drive listings.
- **Shared Drive folder links:** Settings accepts either a raw Drive `folderId` or a shared Google Drive folder URL. Public/shared folders can be browsed without OAuth when access allows it.
- **Shared playback progress:** Server-side bookmarks sync progress between browsers/devices connected to the same SonicBook instance and profile.
- **Bedtime sleep timer:** Toolbar countdown timer with activity reset, auto-pause, auto-resume on activity, screen dimming, and gradual audio fade-out during the final 60 seconds.
- **Cover pipeline:** Downloads covers during normal downloads and can backfill missing covers in an existing library.
- **Settings:** Change language, choose the local library folder, set a sync profile, configure Google Drive, and clear app data/cache.

## Requirements

1. **Python 3.10+**
2. **FFmpeg and FFprobe**
   - Must be available in `PATH`, or configured via `FFMPEG_PATH` and `FFPROBE_PATH`.
   - Windows: `winget install -e --id Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. **Playwright Chromium**
   - Used when normal HTML parsing is not enough.
4. **Python dependencies**
   - Installed from `requirements.txt`, including FastAPI, Playwright, `httpx`, `httpx[http2]` support dependencies, `aiofiles`, `yt-dlp`, Pillow, and keyring support.

## Quick Start

```bash
git clone https://github.com/shafranek-js/SonicBook.git
cd SonicBook
pip install -r requirements.txt
playwright install chromium
python main.py
```

Open `http://localhost:8000`.

If FFmpeg is not in `PATH`, create `.env` from `.env.example` and set:

```env
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
```

## Downloading Books

1. Paste a supported audiobook page URL into the toolbar input.
2. Choose a mode:
   - **M4B (Chapters):** Creates one `.m4b` file with embedded chapters when chapters are available.
   - **Single File:** Downloads one final audio file when the source supports it.
   - **ZIP (Split):** Splits chapters into separate files and stores them in a ZIP archive.
3. For M4B/ZIP, click **Fetch Info** to preview chapters, then confirm download.
4. Watch the progress box:
   - **Downloading:** source fragments/files are being fetched.
   - **Assembling:** FFmpeg or ZIP assembly is producing the final artifact.
5. Completed artifacts and sidecars are moved into the configured local library folder only after validation.

Notes:

- Duplicate downloads for the same source URL reuse the existing active task instead of launching a second conflicting task.
- Direct MP3 chapter downloads support resume when the server honors byte ranges.
- Large direct single-file downloads may use multiple byte ranges when safe. Unsupported or failed probes fall back automatically.
- Audioboo pages are handled through direct ZIP discovery where available; ZIP playback uses the built-in playlist mode.

Optional download tuning:

```env
YTDLP_CONCURRENCY=16
MULTI_CONNECTION_DOWNLOADS=1
MULTI_CONNECTION_MAX_SEGMENTS=4
MULTI_CONNECTION_MIN_BYTES=67108864
```

## Player And Local Library

The left panel contains the current library. It supports local files and Drive files through the `Local` / `Drive` toggle.

Local library behavior:

- Search filters visible books.
- Books are grouped into `Now Listening`, `In Queue`, and `Completed`.
- Playback progress is shown directly on each book row.
- The reset action clears saved progress for a book.
- Completed/not-completed actions update the shared bookmark state.
- Metadata is cached in `library_index.json`, so unchanged large libraries load quickly.

Player behavior:

- M4B chapters appear in the right chapter panel.
- ZIP books are extracted safely into hidden on-demand folders and played as a sequential playlist.
- The chapter panel auto-opens when structured metadata is available.
- Space toggles play/pause; left/right arrows seek.
- OS media keys and lock-screen controls work through the Media Session API when the browser supports it.
- Playback position is saved automatically and restored on the next open.

## Google Drive

SonicBook can use Google Drive in two modes.

### Shared Link Mode

For public/shared Drive folders, open **Settings**, paste either the full folder link or the raw folder ID, then click **Save folder**. SonicBook extracts the canonical folder ID and lists supported audiobook files when Google allows access through the shared link.

This is useful when you want to listen from a computer that does not have the desktop Google Drive sync app installed.

### OAuth Mode

Use OAuth for private folders or account-specific access.

1. Copy `.env.example` to `.env`.
2. Fill in:
   - `GOOGLE_DRIVE_CLIENT_ID`
   - `GOOGLE_DRIVE_CLIENT_SECRET`
   - optionally `GOOGLE_DRIVE_REDIRECT_URI`
3. In Google Cloud Console, configure the OAuth client redirect URI:
   - `http://127.0.0.1:8000/api/google-drive/auth/callback`
4. Restart SonicBook.
5. Open **Settings** and click **Connect**.

Drive library behavior:

- `Stream` plays a supported Drive file through the backend proxy without importing.
- Stream startup shows `Connecting`, `Buffering`, and `Playing` states so long startup does not look idle.
- `Import` downloads the Drive book and sidecars into the local library and shows in-row import progress.
- Already imported Drive books remain marked `Imported`.
- Drive listings use short-lived backend caching for speed; use the refresh button for a live reload.
- Drive playback progress is shared with local progress when both resolve to the same book identity.

## Sync Profile And Bookmarks

SonicBook stores playback progress on the local backend in `bookmarks.json`.

Sync scope:

- Works across browsers and devices connected to the same running SonicBook server.
- Use the same **Sync profile** value in Settings to share progress between your own devices.
- Other users should use a different profile to avoid mixing progress.
- This is not a hosted cloud sync service between separate SonicBook servers.

What is synchronized:

- Current position and duration.
- Track index for ZIP playlists.
- Completed/not-completed state.
- Local and Drive progress when the book identity matches.

## Sleep Timer

The toolbar sleep timer is designed for listening before sleep.

- Click the timer button to enable or disable it.
- Choose a duration from the dropdown. The `1m` option is present for quick testing.
- The countdown resets on browser activity such as mouse, keyboard, wheel, touch, scroll, focus, and visibility changes.
- On Windows, SonicBook also checks system idle time through `/api/system/idle`, so activity outside the browser can reset the timer when available.
- When the timer expires, playback pauses.
- If the timer caused the pause, the next user activity auto-resumes playback and restarts the timer.
- During the final 60 seconds, SonicBook gradually lowers the browser audio element volume to zero.
- Any activity during that final minute cancels fade-out and restores the original user volume.
- Turning the timer off or pausing playback manually restores volume and clears dimming.
- While active, SonicBook tries to dim the display over 5 seconds. Unsupported displays fall back to a black overlay inside the SonicBook browser window.

Brightness notes:

- Built-in Windows displays may support brightness control through WMI/CIM.
- External monitors often do not expose brightness this way.
- Browser clients cannot change monitor brightness directly; system brightness control goes through the local backend.

## Cover Backfill

Existing libraries can be retrofitted with covers after download history is already on disk.

```bash
python backfill_covers.py
```

`cover_aliases.json` can pin known source pages or hard matches for books with weak or ambiguous titles. The backfill flow prefers direct source pages, then falls back to catalog providers and ranks candidates by usable image dimensions.

## Runtime Data

SonicBook creates local runtime files that are intentionally ignored by git:

- `settings.json`
- `bookmarks.json`
- `progress_store.json`
- `library_index.json`
- `.sonicbook-work/`
- downloaded books and temporary staging outputs

Settings and bookmark writes use the shared locked JSON storage layer to reduce race conditions. Google OAuth tokens are protected with Windows DPAPI where available and use keyring-backed secure storage on other platforms when configured.

## Development

Useful commands:

```bash
python -m pytest -q
python -m compileall .
```

The FastAPI entrypoint is `main.py`. Most API logic lives in route modules under `routes/`, while media work is split across `download_sources.py`, `media_assembly.py`, `media_assets.py`, `library_storage.py`, and `library_finalization.py`.

See `handoff.md` for architecture details and `TODO.md` for historical completed work and remaining planning context.

## License

MIT License. Free for personal use.
