import os
import uuid
import asyncio
import logging
import json
import html
import mimetypes
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from urllib.parse import quote
import uvicorn
import aiofiles
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import scraper
import processor
import library_service
import progress_service
import zip_service
import google_drive_service
import bookmark_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(config.DEBUG_LOG, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
STREAM_CHUNK_SIZE = 1024 * 1024

MEDIA_TYPE_OVERRIDES = {
    ".m4b": "audio/mp4",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".zip": "application/zip",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".json": "application/json",
}


def guess_media_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in MEDIA_TYPE_OVERRIDES:
        return MEDIA_TYPE_OVERRIDES[ext]
    guessed_type, _ = mimetypes.guess_type(file_path)
    return guessed_type or "application/octet-stream"


def build_inline_content_disposition(file_path: str) -> str:
    return f"inline; filename*=utf-8''{quote(os.path.basename(file_path))}"


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None

    units, _, raw_range = range_header.partition("=")
    if units.strip().lower() != "bytes" or not raw_range:
        raise HTTPException(status_code=416, detail="Invalid range unit")

    first_range = raw_range.split(",", 1)[0].strip()
    start_str, sep, end_str = first_range.partition("-")
    if not sep:
        raise HTTPException(status_code=416, detail="Invalid range format")

    try:
        if start_str:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        else:
            suffix_length = int(end_str)
            if suffix_length <= 0:
                raise HTTPException(status_code=416, detail="Invalid range suffix")
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid byte range") from exc

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    end = min(end, file_size - 1)
    return start, end


async def iter_file_range(file_path: str, start: int, end: int):
    async with aiofiles.open(file_path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = await f.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

def resolve_download_path(file_name: str) -> str:
    if not file_name:
        raise HTTPException(status_code=400, detail="Invalid file path")

    normalized_name = os.path.normpath(file_name)
    drive, _ = os.path.splitdrive(normalized_name)
    if drive or os.path.isabs(file_name) or os.path.isabs(normalized_name):
        raise HTTPException(status_code=400, detail="Invalid file path")

    downloads_root = os.path.abspath(config.DOWNLOADS_DIR)
    candidate_path = os.path.abspath(os.path.join(downloads_root, normalized_name))
    try:
        if os.path.commonpath([downloads_root, candidate_path]) != downloads_root:
            raise HTTPException(status_code=400, detail="Invalid file path")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    return candidate_path

def validate_book_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid book URL")
    return candidate

def should_suppress_asyncio_noise(context: dict) -> bool:
    exc = context.get("exception")
    if not isinstance(exc, ConnectionResetError):
        return False

    if getattr(exc, "winerror", None) != 10054:
        return False

    handle_repr = repr(context.get("handle", ""))
    return "_ProactorBasePipeTransport._call_connection_lost" in handle_repr

def install_asyncio_exception_filter():
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def handler(current_loop, context):
        if should_suppress_asyncio_noise(context):
            return

        if previous_handler is not None:
            previous_handler(current_loop, context)
            return

        current_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    return previous_handler

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    mode: str = "m4b"


class GoogleDriveFolderRequest(BaseModel):
    folder_id: str = ""


class PlaybackProfileRequest(BaseModel):
    profile_id: str = ""


class GoogleDriveImportRequest(BaseModel):
    file_id: str
    metadata_file_id: str = ""
    cover_file_id: str = ""
    file_name: str = ""
    metadata_file_name: str = ""
    cover_file_name: str = ""
    resource_key: str = ""
    metadata_resource_key: str = ""
    cover_resource_key: str = ""


class BookmarkUpdateRequest(BaseModel):
    time: float = 0.0
    duration: float = 0.0
    track: int = 0
    file_name: str = ""
    source: str = ""
    completed: bool | None = None


class ActivePlaybackStateRequest(BaseModel):
    book_id: str = ""
    file_name: str = ""
    source: str = ""
    drive_file_id: str = ""
    drive_metadata_file_id: str = ""
    drive_cover_file_id: str = ""
    drive_resource_key: str = ""
    drive_metadata_resource_key: str = ""
    drive_cover_resource_key: str = ""
    size_bytes: int = 0

async def cleanup_task():
    """Background task to remove old store entries (files are kept permanently)"""
    while True:
        try:
            progress_service.cleanup_expired_progress(config.STORE_EXPIRE_SECONDS)
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        await asyncio.sleep(600) # Run every 10 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    import shutil
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)
    config.ensure_runtime_directories()
    
    config.ensure_ffmpeg_binaries()
    loop = asyncio.get_running_loop()
    previous_exception_handler = install_asyncio_exception_filter()
    task = asyncio.create_task(cleanup_task())
    await scraper.init_browser()
    yield
    task.cancel()
    loop.set_exception_handler(previous_exception_handler)
    await scraper.close_browser()

app = FastAPI(title="SonicBook", lifespan=lifespan)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

from fastapi.responses import JSONResponse

@app.middleware("http")
async def security_token_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        token = request.headers.get("X-SonicBook-Token")
        if not token:
            token = request.query_params.get("token")

        if token != config.API_TOKEN:
            return JSONResponse(status_code=403, content={"detail": "Forbidden: Invalid API Token"})

    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def index():
    async with aiofiles.open("index.html", "r", encoding="utf-8") as f:
        content = await f.read()
        content = content.replace("</head>", f'<script>window.API_TOKEN="{config.API_TOKEN}";</script></head>')
        return content


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=307)

@app.get("/api/settings/folder")
async def get_folder():
    return {"folder": config.DOWNLOADS_DIR}


@app.get("/api/settings/playback-profile")
async def get_playback_profile():
    return {
        **config.get_playback_profile_status(),
        **bookmark_service.get_state_storage_status(),
    }


@app.post("/api/settings/playback-profile")
async def save_playback_profile(request: PlaybackProfileRequest):
    try:
        config.save_playback_profile_id(request.profile_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "success",
        **config.get_playback_profile_status(),
        **bookmark_service.get_state_storage_status(),
    }


@app.post("/api/settings/choose_folder")
async def choose_folder():
    import sys
    script = """
import sys
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.wm_attributes('-topmost', 1)
folder = filedialog.askdirectory(initialdir=sys.argv[1], title="Select Download Folder")
root.destroy()
if folder:
    sys.stdout.write(folder)
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, config.DOWNLOADS_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    selected = stdout.decode("utf-8", errors="replace").strip()
    
    if selected:
        # Use absolute path and fix slashes
        selected = os.path.abspath(selected)
        if config.save_downloads_dir(selected):
            return {"status": "success", "folder": selected}
    
    return {"status": "cancelled", "folder": config.DOWNLOADS_DIR}


@app.get("/api/google-drive/status")
async def google_drive_status():
    return google_drive_service.get_google_drive_status()


@app.get("/api/google-drive/auth/url")
async def google_drive_auth_url():
    try:
        return google_drive_service.build_google_drive_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/google-drive/auth/callback", response_class=HTMLResponse)
async def google_drive_auth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        message = html.escape(error_description or error)
        return HTMLResponse(
            f"<html><body><h2>Google Drive connection failed</h2><p>{message}</p></body></html>",
            status_code=400,
        )

    try:
        auth = await google_drive_service.exchange_code_for_google_tokens(code, state)
    except Exception as exc:
        logger.exception("Google Drive OAuth callback failed")
        message = html.escape(str(exc))
        return HTMLResponse(
            f"<html><body><h2>Google Drive connection failed</h2><p>{message}</p></body></html>",
            status_code=400,
        )

    account_name = html.escape(auth.get("account_name") or auth.get("account_email") or "Google account")
    return HTMLResponse(
        "<html><body>"
        "<h2>Google Drive connected</h2>"
        f"<p>Connected as {account_name}.</p>"
        "<p>You can close this window and return to SonicBook.</p>"
        "</body></html>"
    )


@app.post("/api/google-drive/disconnect")
async def google_drive_disconnect():
    if not google_drive_service.disconnect_google_drive():
        raise HTTPException(status_code=500, detail="Failed to clear Google Drive auth settings")
    return {"status": "success"}


@app.post("/api/google-drive/folder")
async def google_drive_save_folder(request: GoogleDriveFolderRequest):
    try:
        folder_id = google_drive_service.save_google_drive_folder_id(request.folder_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "folder_id": folder_id}


@app.get("/api/google-drive/library")
async def google_drive_library(folder_id: str = "", refresh: bool = False):
    try:
        files = await google_drive_service.list_google_drive_library_files_cached(folder_id, force_refresh=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"files": files}


@app.post("/api/google-drive/import")
async def google_drive_import(request: GoogleDriveImportRequest):
    try:
        result = await google_drive_service.import_google_drive_file(
            request.file_id,
            request.metadata_file_id,
            request.cover_file_id,
            request.file_name,
            request.metadata_file_name,
            request.cover_file_name,
            request.resource_key,
            request.metadata_resource_key,
            request.cover_resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", **result}


@app.get("/api/google-drive/metadata/{file_id}")
async def google_drive_metadata(
    file_id: str,
    metadata_file_id: str = "",
    cover_file_id: str = "",
    file_name: str = "",
    resource_key: str = "",
    metadata_resource_key: str = "",
    cover_resource_key: str = "",
):
    try:
        return await google_drive_service.build_google_drive_metadata(
            file_id,
            metadata_file_id,
            cover_file_id,
            file_name,
            resource_key,
            metadata_resource_key,
            cover_resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/google-drive/files/{file_id}/probe")
async def google_drive_probe_file(file_id: str, resource_key: str = ""):
    try:
        return await google_drive_service.probe_google_drive_stream(file_id, resource_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        logger.exception("Google Drive stream probe failed")
        raise HTTPException(status_code=502, detail="Google Drive file probe failed") from exc


@app.get("/api/google-drive/files/{file_id}/stream")
async def google_drive_stream_file(file_id: str, request: Request, resource_key: str = ""):
    try:
        client, response, headers = await google_drive_service.open_google_drive_stream(
            file_id,
            request.headers.get("range", ""),
            resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async def stream_generator():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_generator(),
        status_code=response.status_code,
        headers=headers,
        media_type=response.headers.get("content-type"),
    )

@app.post("/api/info")
async def get_info(request: InfoRequest):
    book_url = validate_book_url(request.url)
    try:
        m3u8, title, chapters, cover = await scraper.get_book_info(book_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not m3u8:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"title": title, "chapters": chapters, "cover": cover}

@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    book_url = validate_book_url(request.url)
    existing_task = progress_service.find_active_task_by_source(book_url)
    if existing_task:
        task_id, _ = existing_task
        return {"task_id": task_id, "reused": True}
    task_id = str(uuid.uuid4())
    progress_service.set_progress(task_id, progress_service.create_progress_entry(source_url=book_url, mode=request.mode))
    background_tasks.add_task(process_book, task_id, book_url, request.mode)
    return {"task_id": task_id}

async def process_book(task_id, url, mode):
    try:
        # 1. Get info again (or cache it)
        m3u8, title, chapters, cover = await scraper.get_book_info(url)
        if not m3u8:
            progress_service.update_progress_entry(task_id, status="error", message="Audio stream not found")
            return

        progress_service.update_progress_entry(task_id, status="processing", phase="downloading", percent=0.0)

        # Define callback for progress
        async def update_progress(pct, curr, total, status=None, phase=None):
            fields = {}
            if status is not None: fields["status"] = status
            if phase is not None: fields["phase"] = phase
            if pct is not None: fields["percent"] = pct
            if curr is not None: fields["current_frag"] = curr
            if total is not None: fields["total_frags"] = total
            if fields:
                progress_service.update_progress_entry(task_id, **fields)

        # 2. Download and process
        clean_title = processor.sanitize_filename(title)
        final_file = await processor.run_fast_download(
            task_id, m3u8, clean_title, chapters, mode, update_progress, cover, url
        )
        if final_file:
            progress_service.update_progress_entry(
                task_id,
                status="success",
                phase="complete",
                percent=100.0,
                file_name=final_file
            )
        else:
            progress_service.update_progress_entry(task_id, status="error")
    except RuntimeError as exc:
        logger.exception("Background task failed for %s", task_id)
        progress_service.update_progress_entry(task_id, status="error", message=str(exc))
    except Exception:
        logger.exception("Background task failed for %s", task_id)
        progress_service.update_progress_entry(task_id, status="error", message="Background task failed")

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    return progress_service.get_progress(task_id)

@app.get("/api/progress/stream/{task_id}")
async def progress_stream(task_id: str, request: Request):
    async def event_generator():
        last_payload = None
        try:
            while True:
                if await request.is_disconnected():
                    break

                data = progress_service.get_progress(task_id)
                payload = json.dumps(data, ensure_ascii=False, sort_keys=True)

                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"

                if data.get("status") in ["success", "error", "not_found"]:
                    break

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.debug("SSE progress stream cancelled for task %s", task_id)
        except (ConnectionResetError, BrokenPipeError, RuntimeError):
            logger.debug("SSE progress stream disconnected for task %s", task_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/bookmarks")
async def get_bookmarks():
    return {
        "bookmarks": bookmark_service.list_bookmarks(),
        "last_active": bookmark_service.get_last_active(),
    }


@app.get("/api/bookmarks/{book_id:path}")
async def get_bookmark(book_id: str):
    return {"bookmark": bookmark_service.get_bookmark(book_id)}


@app.post("/api/bookmarks/{book_id:path}")
async def save_bookmark(book_id: str, request: BookmarkUpdateRequest):
    try:
        bookmark = bookmark_service.save_bookmark(book_id, request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "bookmark": bookmark}


@app.delete("/api/bookmarks/{book_id:path}")
async def delete_bookmark(book_id: str):
    if not bookmark_service.delete_bookmark(book_id):
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")
    return {"status": "success"}


@app.post("/api/playback/active")
async def save_active_playback(request: ActivePlaybackStateRequest):
    try:
        playback_state = bookmark_service.save_last_active(request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "last_active": playback_state}

@app.get("/api/library")
async def get_library():
    return {"files": library_service.list_library_files(config.DOWNLOADS_DIR)}


@app.get("/api/library/imported-book-ids")
async def get_imported_book_ids():
    return {"book_ids": library_service.list_library_book_ids(config.DOWNLOADS_DIR)}

@app.get("/api/files/{file_name:path}")
async def download_file(file_name: str, request: Request):
    file_path = resolve_download_path(file_name)
    if await asyncio.to_thread(os.path.exists, file_path):
        media_type = guess_media_type(file_path)
        common_headers = {
            "accept-ranges": "bytes",
            "content-disposition": build_inline_content_disposition(file_path),
        }
        file_size = await asyncio.to_thread(os.path.getsize, file_path)
        range_header = request.headers.get("range", "")
        byte_range = parse_range_header(range_header, file_size) if range_header else None
        if byte_range is not None:
            start, end = byte_range
            headers = {
                **common_headers,
                "content-length": str(end - start + 1),
                "content-range": f"bytes {start}-{end}/{file_size}",
            }
            return StreamingResponse(
                iter_file_range(file_path, start, end),
                status_code=206,
                media_type=media_type,
                headers=headers,
            )

        response = FileResponse(
            path=file_path,
            media_type=media_type,
            filename=os.path.basename(file_path),
            content_disposition_type="inline",
        )
        response.headers["accept-ranges"] = "bytes"
        response.headers["content-disposition"] = common_headers["content-disposition"]
        return response
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/metadata/{file_name}")
async def get_metadata(file_name: str):
    file_path = resolve_download_path(file_name)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Handle ZIP files (Playlist mode)
    if file_name.endswith('.zip'):
        payload = await zip_service.build_zip_metadata(file_path, file_name, config.DOWNLOADS_DIR)
        if isinstance(payload, dict):
            size_bytes = await asyncio.to_thread(os.path.getsize, file_path)
            payload["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=size_bytes, metadata=payload)
        return payload

    # Handle standard M4B/MP3 with JSON metadata
    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if await asyncio.to_thread(os.path.exists, json_path):
        try:
            async with aiofiles.open(json_path, "r", encoding="utf-8") as f:
                content = await f.read()
                payload = json.loads(content)
            if isinstance(payload, dict):
                size_bytes = await asyncio.to_thread(os.path.getsize, file_path)
                payload["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=size_bytes, metadata=payload)
                return payload
        except Exception:
            logger.exception("Failed to read metadata sidecar: %s", json_path)
            raise HTTPException(status_code=500, detail="Metadata read failed")
    raise HTTPException(status_code=404, detail="Metadata not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
