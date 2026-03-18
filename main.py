import os
import uuid
import time
import asyncio
import logging
import json
import zipfile
from contextlib import asynccontextmanager
from urllib.parse import urlparse
import uvicorn
import aiofiles
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import scraper
import processor

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

# In-memory progress tracking
# task_id -> {status, percent, current_frag, total_frags, file_name, timestamp}
progress_store = {}
terminal_progress_statuses = {"success", "error", "not_found"}

# Locks for async operations
zip_extraction_locks = {}

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

def update_progress_entry(task_id: str, **fields):
    entry = progress_store.get(task_id)
    if entry is None:
        return None

    entry.update(fields)
    entry["timestamp"] = time.time()
    return entry

def get_zip_extraction_lock(extract_dir_name: str) -> asyncio.Lock:
    lock = zip_extraction_locks.get(extract_dir_name)
    if lock is None:
        lock = asyncio.Lock()
        zip_extraction_locks[extract_dir_name] = lock
    return lock

def extract_zip_archive(zip_path: str, extract_dir_path: str):
    with zipfile.ZipFile(zip_path, 'r') as archive:
        archive.extractall(extract_dir_path)

def load_sidecar_metadata(file_path: str) -> dict | None:
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read sidecar metadata: %s", json_path)
        return None

async def ensure_zip_extracted(zip_path: str, extract_dir_name: str, extract_dir_path: str):
    if os.path.exists(extract_dir_path):
        return

    lock = get_zip_extraction_lock(extract_dir_name)
    async with lock:
        if os.path.exists(extract_dir_path):
            return

        try:
            await asyncio.to_thread(extract_zip_archive, zip_path, extract_dir_path)
        except Exception as e:
            logger.error(f"Failed to extract zip {zip_path}: {e}")
            raise HTTPException(status_code=500, detail="Failed to extract ZIP for playback")

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    mode: str = "m4b"

async def cleanup_task():
    """Background task to remove old store entries (files are kept permanently)"""
    while True:
        try:
            now = time.time()
            
            # Expire only terminal tasks; active downloads should remain visible.
            to_delete = [
                tid for tid, data in list(progress_store.items())
                if data.get("status") in terminal_progress_statuses
                and now - data.get('timestamp', 0) > config.STORE_EXPIRE_SECONDS
            ]
            for tid in to_delete:
                del progress_store[tid]
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        await asyncio.sleep(600) # Run every 10 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/", response_class=HTMLResponse)
async def index():
    async with aiofiles.open("index.html", "r", encoding="utf-8") as f:
        return await f.read()

@app.get("/api/settings/folder")
async def get_folder():
    return {"folder": config.DOWNLOADS_DIR}

@app.post("/api/settings/choose_folder")
async def choose_folder():
    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        folder = filedialog.askdirectory(initialdir=config.DOWNLOADS_DIR, title="Select Download Folder")
        root.destroy()
        return folder

    loop = asyncio.get_running_loop()
    selected = await loop.run_in_executor(None, open_dialog)
    
    if selected:
        # Use absolute path and fix slashes
        selected = os.path.abspath(selected)
        if config.save_downloads_dir(selected):
            return {"status": "success", "folder": selected}
    
    return {"status": "cancelled", "folder": config.DOWNLOADS_DIR}

@app.post("/api/info")
async def get_info(request: InfoRequest):
    book_url = validate_book_url(request.url)
    m3u8, title, chapters, cover = await scraper.get_book_info(book_url)
    if not m3u8:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"title": title, "chapters": chapters, "cover": cover}

@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    book_url = validate_book_url(request.url)
    task_id = str(uuid.uuid4())
    progress_store[task_id] = {
        "status": "searching", 
        "percent": 0.0, 
        "current_frag": 0, 
        "total_frags": 0, 
        "file_name": "",
        "timestamp": time.time()
    }
    background_tasks.add_task(process_book, task_id, book_url, request.mode)
    return {"task_id": task_id}

async def process_book(task_id, url, mode):
    try:
        # 1. Get info again (or cache it)
        m3u8, title, chapters, cover = await scraper.get_book_info(url)
        if not m3u8:
            update_progress_entry(task_id, status="error")
            return

        update_progress_entry(task_id, status="processing")

        # Define callback for progress
        async def update_progress(pct, curr, total, status=None):
            fields = {}
            if status is not None: fields["status"] = status
            if pct is not None: fields["percent"] = pct
            if curr is not None: fields["current_frag"] = curr
            if total is not None: fields["total_frags"] = total
            if fields:
                update_progress_entry(task_id, **fields)

        # 2. Download and process
        clean_title = processor.sanitize_filename(title)
        final_file = await processor.run_fast_download(
            task_id, m3u8, clean_title, chapters, mode, update_progress, cover, url
        )
        if final_file:
            update_progress_entry(
                task_id,
                status="success",
                percent=100.0,
                file_name=final_file
            )
        else:
            update_progress_entry(task_id, status="error")
    except Exception:
        logger.exception("Background task failed for %s", task_id)
        update_progress_entry(task_id, status="error")

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    return progress_store.get(task_id, {"status": "not_found"})

@app.get("/api/progress/stream/{task_id}")
async def progress_stream(task_id: str, request: Request):
    async def event_generator():
        last_percent = -1
        last_status = None
        while True:
            if await request.is_disconnected():
                break
                
            data = progress_store.get(task_id, {"status": "not_found"})
            
            # Only send update if something changed
            if data.get("percent") != last_percent or data.get("status") != last_status:
                last_percent = data.get("percent", -1)
                last_status = data.get("status")
                import json
                yield f"data: {json.dumps(data)}\n\n"
            
            if data.get("status") in ["success", "error", "not_found"]:
                # Send one final update just to be sure, then stop stream
                yield f"data: {json.dumps(data)}\n\n"
                break
                
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/library")
async def get_library():
    if not os.path.exists(config.DOWNLOADS_DIR):
        return {"files": []}
        
    files = []
    for f in os.listdir(config.DOWNLOADS_DIR):
        if f.endswith(('.m4b', '.mp3', '.zip', '.mp4', '.m4a')):
            file_path = os.path.join(config.DOWNLOADS_DIR, f)
            size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
            has_meta = os.path.exists(os.path.join(config.DOWNLOADS_DIR, f"{os.path.splitext(f)[0]}.json"))
            files.append({
                "name": f,
                "size_mb": size_mb,
                "has_meta": has_meta,
                "mtime": os.path.getmtime(file_path)
            })
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return {"files": files}

@app.get("/api/files/{file_name:path}")
async def download_file(file_name: str):
    file_path = resolve_download_path(file_name)
    if os.path.exists(file_path):
        # FileResponse natively supports HTTP Range requests for streaming audio
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/metadata/{file_name}")
async def get_metadata(file_name: str):
    file_path = resolve_download_path(file_name)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Handle ZIP files (Playlist mode)
    if file_name.endswith('.zip'):
        zip_path = file_path
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=404, detail="ZIP file not found")
            
        extract_dir_name = f".extracted_{base_name}"
        extract_dir_path = os.path.join(config.DOWNLOADS_DIR, extract_dir_name)
        
        # Extract if not already extracted
        await ensure_zip_extracted(zip_path, extract_dir_name, extract_dir_path)
                
        # Build playlist
        playlist = []
        if os.path.exists(extract_dir_path):
            files = sorted(os.listdir(extract_dir_path))
            for f in files:
                if f.endswith(('.mp3', '.m4a', '.mp4')):
                    title = os.path.splitext(f)[0]
                    # path relative to DOWNLOADS_DIR
                    rel_path = f"{extract_dir_name}/{f}"
                    playlist.append({"title": title, "file": rel_path})
                    
        payload = {
            "title": base_name,
            "mode": "zip",
            "playlist": playlist
        }
        sidecar_meta = load_sidecar_metadata(file_path)
        if sidecar_meta:
            payload["title"] = sidecar_meta.get("title") or payload["title"]
            payload["cover_url"] = sidecar_meta.get("cover_url")
            payload["local_cover"] = sidecar_meta.get("local_cover")
            payload["file_name"] = sidecar_meta.get("file_name", file_name)

        return payload

    # Handle standard M4B/MP3 with JSON metadata
    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if os.path.exists(json_path):
        return FileResponse(path=json_path)
    raise HTTPException(status_code=404, detail="Metadata not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
