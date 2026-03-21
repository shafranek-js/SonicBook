import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
import aiofiles
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import config
import scraper
import progress_service
from routes.bookmark_routes import router as bookmark_router
from routes.download_routes import router as download_router
from routes.google_drive_routes import router as google_drive_router
from routes.library_routes import router as library_router
from routes.progress_routes import router as progress_router
from routes.settings_routes import router as settings_router

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
app.include_router(settings_router)
app.include_router(progress_router)
app.include_router(bookmark_router)
app.include_router(library_router)
app.include_router(google_drive_router)
app.include_router(download_router)

@app.get("/", response_class=HTMLResponse)
async def index():
    async with aiofiles.open("index.html", "r", encoding="utf-8") as f:
        return await f.read()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
