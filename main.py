import os
import uuid
import time
import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
import aiofiles
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
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
            
            # Clean progress store only
            to_delete = [tid for tid, data in progress_store.items() 
                         if now - data.get('timestamp', 0) > config.STORE_EXPIRE_SECONDS]
            for tid in to_delete:
                del progress_store[tid]
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        await asyncio.sleep(600) # Run every 10 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_task())
    yield
    task.cancel()

app = FastAPI(title="SonicBook", lifespan=lifespan)

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
    m3u8, title, chapters = await scraper.get_book_info(request.url)
    if not m3u8:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"title": title, "chapters": chapters}

@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    progress_store[task_id] = {
        "status": "searching", 
        "percent": 0.0, 
        "current_frag": 0, 
        "total_frags": 0, 
        "file_name": "",
        "timestamp": time.time()
    }
    background_tasks.add_task(process_book, task_id, request.url, request.mode)
    return {"task_id": task_id}

async def process_book(task_id, url, mode):
    # 1. Get info again (or cache it)
    m3u8, title, chapters = await scraper.get_book_info(url)
    if not m3u8:
        progress_store[task_id]["status"] = "error"
        return

    progress_store[task_id]["status"] = "processing"
    
    # Define callback for progress
    async def update_progress(pct, curr, total, status=None):
        if status is not None: progress_store[task_id]["status"] = status
        if pct is not None: progress_store[task_id]["percent"] = pct
        if curr is not None: progress_store[task_id]["current_frag"] = curr
        if total is not None: progress_store[task_id]["total_frags"] = total

    # 2. Download and process
    clean_title = processor.sanitize_filename(title)
    final_file = await processor.run_fast_download(
        task_id, m3u8, clean_title, chapters, mode, update_progress
    )
    
    if final_file:
        progress_store[task_id].update({
            "status": "success",
            "percent": 100.0,
            "file_name": final_file,
            "timestamp": time.time() # Refresh for retention
        })
    else:
        progress_store[task_id]["status"] = "error"

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    return progress_store.get(task_id, {"status": "not_found"})

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
    # Prevent directory traversal attacks
    if ".." in file_name or file_name.startswith("/") or file_name.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid file path")
        
    file_path = os.path.join(config.DOWNLOADS_DIR, file_name)
    if os.path.exists(file_path):
        # FileResponse natively supports HTTP Range requests for streaming audio
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/metadata/{file_name}")
async def get_metadata(file_name: str):
    base_name = os.path.splitext(file_name)[0]
    
    # Handle ZIP files (Playlist mode)
    if file_name.endswith('.zip'):
        zip_path = os.path.join(config.DOWNLOADS_DIR, file_name)
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=404, detail="ZIP file not found")
            
        extract_dir_name = f".extracted_{base_name}"
        extract_dir_path = os.path.join(config.DOWNLOADS_DIR, extract_dir_name)
        
        # Extract if not already extracted
        if not os.path.exists(extract_dir_path):
            import zipfile
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(extract_dir_path)
            except Exception as e:
                logger.error(f"Failed to extract zip {zip_path}: {e}")
                raise HTTPException(status_code=500, detail="Failed to extract ZIP for playback")
                
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
                    
        return {
            "title": base_name,
            "mode": "zip",
            "playlist": playlist
        }

    # Handle standard M4B/MP3 with JSON metadata
    json_path = os.path.join(config.DOWNLOADS_DIR, f"{base_name}.json")
    if os.path.exists(json_path):
        return FileResponse(path=json_path)
    raise HTTPException(status_code=404, detail="Metadata not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
