import logging
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from api_models import BookInfoResponse, DownloadRequest, DownloadStartResponse, InfoRequest
import download_workflow
import progress_service
import scraper
from route_helpers import build_user_error_message, validate_book_url


logger = logging.getLogger(__name__)
router = APIRouter()
MAX_ACTIVE_DOWNLOAD_TASKS = 2
SUPPORTED_DOWNLOAD_MODES = {"m4b", "mp3", "zip"}


@router.post("/api/info", response_model=BookInfoResponse)
async def get_info(request: InfoRequest):
    book_url = validate_book_url(request.url)
    try:
        m3u8, title, chapters, cover = await scraper.get_book_info(book_url)
    except scraper.ScraperError as exc:
        logger.exception("Book info scraping failed for %s", book_url)
        raise HTTPException(status_code=502, detail=build_user_error_message(exc, "Failed to fetch book info.")) from exc
    except httpx.TimeoutException as exc:
        logger.exception("Book info request timed out for %s", book_url)
        raise HTTPException(status_code=504, detail="Timed out while fetching book info.") from exc
    except httpx.RequestError as exc:
        logger.exception("Book info network request failed for %s", book_url)
        raise HTTPException(status_code=502, detail="Network error while fetching book info.") from exc
    except Exception as exc:
        logger.exception("Book info scraping failed for %s", book_url)
        raise HTTPException(status_code=500, detail=build_user_error_message(exc, "Failed to fetch book info.")) from exc

    if not m3u8:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    download_workflow.cache_book_info(book_url, m3u8=m3u8, title=title, chapters=chapters, cover=cover)
    return {"title": title, "chapters": chapters, "cover": cover}


@router.post("/api/download", response_model=DownloadStartResponse)
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    book_url = validate_book_url(request.url)
    mode = (request.mode or "").strip().lower()
    if mode not in SUPPORTED_DOWNLOAD_MODES:
        raise HTTPException(status_code=400, detail="Unsupported download mode.")

    existing_task = progress_service.find_active_task_by_source(book_url)
    if existing_task:
        task_id, _ = existing_task
        return {"task_id": task_id, "reused": True}

    if progress_service.count_active_tasks() >= MAX_ACTIVE_DOWNLOAD_TASKS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many active downloads. Wait for one of the current {MAX_ACTIVE_DOWNLOAD_TASKS} tasks to finish.",
        )

    task_id = str(uuid.uuid4())
    progress_service.set_progress(task_id, progress_service.create_progress_entry(source_url=book_url, mode=mode))
    background_tasks.add_task(download_workflow.process_book, task_id, book_url, mode, build_user_error_message)
    return {"task_id": task_id}
