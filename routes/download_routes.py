import logging
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

import processor
import progress_service
import scraper

logger = logging.getLogger(__name__)
router = APIRouter(tags=["downloads"])


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    mode: str = "m4b"


def validate_book_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid book URL")
    return candidate


@router.post("/api/info")
async def get_info(request: InfoRequest):
    book_url = validate_book_url(request.url)
    try:
        m3u8, title, chapters, cover = await scraper.get_book_info(book_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not m3u8:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"title": title, "chapters": chapters, "cover": cover}


@router.post("/api/download")
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
        m3u8, title, chapters, cover = await scraper.get_book_info(url)
        if not m3u8:
            progress_service.update_progress_entry(task_id, status="error", message="Audio stream not found")
            return

        progress_service.update_progress_entry(task_id, status="processing", phase="downloading", percent=0.0)

        async def update_progress(pct, curr, total, status=None, phase=None):
            fields = {}
            if status is not None:
                fields["status"] = status
            if phase is not None:
                fields["phase"] = phase
            if pct is not None:
                fields["percent"] = pct
            if curr is not None:
                fields["current_frag"] = curr
            if total is not None:
                fields["total_frags"] = total
            if fields:
                progress_service.update_progress_entry(task_id, **fields)

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
                file_name=final_file,
            )
        else:
            progress_service.update_progress_entry(task_id, status="error")
    except RuntimeError as exc:
        logger.exception("Background task failed for %s", task_id)
        progress_service.update_progress_entry(task_id, status="error", message=str(exc))
    except Exception:
        logger.exception("Background task failed for %s", task_id)
        progress_service.update_progress_entry(task_id, status="error", message="Background task failed")
