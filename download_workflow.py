import logging
import time

import httpx

import processor
import progress_service
import scraper


logger = logging.getLogger(__name__)
BOOK_INFO_CACHE_TTL_SECONDS = 15 * 60
book_info_cache = {}


def get_cached_book_info(book_url: str):
    payload = book_info_cache.get(book_url)
    if not isinstance(payload, dict):
        return None
    expires_at = float(payload.get("expires_at") or 0)
    if expires_at <= time.time():
        book_info_cache.pop(book_url, None)
        return None
    return dict(payload.get("info") or {})


def cache_book_info(book_url: str, *, m3u8: str, title: str, chapters: list, cover: str | None):
    book_info_cache[book_url] = {
        "expires_at": time.time() + BOOK_INFO_CACHE_TTL_SECONDS,
        "info": {
            "m3u8": m3u8,
            "title": title,
            "chapters": chapters,
            "cover": cover,
        },
    }


def invalidate_book_info(book_url: str):
    book_info_cache.pop(book_url, None)


async def process_book(task_id: str, url: str, mode: str, build_user_error_message):
    try:
        cached_info = get_cached_book_info(url)
        if cached_info:
            m3u8 = cached_info.get("m3u8")
            title = cached_info.get("title") or "audiobook"
            chapters = cached_info.get("chapters") or []
            cover = cached_info.get("cover")
        else:
            m3u8, title, chapters, cover = await scraper.get_book_info(url)
            if not m3u8:
                progress_service.update_progress_entry(
                    task_id,
                    status="error",
                    message="Audio stream not found for this book.",
                )
                return
            cache_book_info(url, m3u8=m3u8, title=title, chapters=chapters, cover=cover)

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
            invalidate_book_info(url)
            progress_service.update_progress_entry(
                task_id,
                status="success",
                phase="complete",
                percent=100.0,
                file_name=final_file,
            )
        else:
            invalidate_book_info(url)
            progress_service.update_progress_entry(
                task_id,
                status="error",
                message="Download pipeline failed before producing a final file.",
            )
    except processor.ProcessingError as exc:
        logger.exception("Background processing error for %s", task_id)
        invalidate_book_info(url)
        progress_service.update_progress_entry(
            task_id,
            status="error",
            message=build_user_error_message(exc, "Processing pipeline failed."),
        )
    except scraper.ScraperError as exc:
        logger.exception("Background scraper failure for %s", task_id)
        invalidate_book_info(url)
        progress_service.update_progress_entry(
            task_id,
            status="error",
            message=build_user_error_message(exc, "Failed to scrape book info."),
        )
    except httpx.TimeoutException:
        logger.exception("Background download timed out for %s", task_id)
        invalidate_book_info(url)
        progress_service.update_progress_entry(
            task_id,
            status="error",
            message="Timed out while scraping or downloading the book.",
        )
    except httpx.RequestError:
        logger.exception("Background download network error for %s", task_id)
        invalidate_book_info(url)
        progress_service.update_progress_entry(
            task_id,
            status="error",
            message="Network error while downloading the book.",
        )
    except Exception as exc:
        logger.exception("Background task failed for %s", task_id)
        invalidate_book_info(url)
        progress_service.update_progress_entry(
            task_id,
            status="error",
            message=build_user_error_message(exc, "Background task failed."),
        )
