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
    """Background task to remove old files and store entries"""
    while True:
        try:
            now = time.time()
            
            # Clean progress store
            to_delete = [tid for tid, data in progress_store.items() 
                         if now - data.get('timestamp', 0) > config.STORE_EXPIRE_SECONDS]
            for tid in to_delete:
                del progress_store[tid]
            
            # Clean downloads directory
            if os.path.exists(config.DOWNLOADS_DIR):
                for f in os.listdir(config.DOWNLOADS_DIR):
                    fpath = os.path.join(config.DOWNLOADS_DIR, f)
                    if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > config.FILE_EXPIRE_SECONDS:
                        try: os.remove(fpath)
                        except Exception as e: logger.error(f"Failed to remove file {fpath}: {e}")
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

@app.get("/api/files/{file_name}")
async def download_file(file_name: str):
    file_path = os.path.join(config.DOWNLOADS_DIR, file_name)
    if os.path.exists(file_path):
        # We don't delete immediately anymore, cleanup_task handles it
        return FileResponse(path=file_path, filename=file_name)
    raise HTTPException(status_code=404, detail="File expired or not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
