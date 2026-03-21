import json
import logging
import os
import shutil

import aiofiles
import httpx

from artifact_builders import (
    build_m4b_with_chapters,
    build_zip_from_chapters,
    download_cover_artifact,
)
from media_helpers import log_debug, move_to_library, prepare_task_work_dir, sanitize_filename
from source_downloaders import download_direct_urls, download_stream_with_ytdlp


logger = logging.getLogger(__name__)


class ProcessingError(RuntimeError):
    pass


async def run_fast_download(task_id, m3u8_url, title_base, chapters, mode, progress_callback, cover_url=None, source_url=None):
    total_frags = 0
    task_work_dir = prepare_task_work_dir(task_id)
    source = ""
    source_ext = ""

    async def report_assembly_progress(percent, current=None, total=None):
        await progress_callback(percent, current, total, status="assembling", phase="assembling")

    if m3u8_url.startswith("DIRECT_URLS:"):
        urls = m3u8_url.replace("DIRECT_URLS:", "").split(",")
        total_frags = len(urls)
        temp_dir = os.path.join(task_work_dir, "direct-download")
        source = await download_direct_urls(urls, temp_dir, task_id, progress_callback)
        if not source:
            raise ProcessingError("Direct audio download failed after multiple retries.")
        source_ext = ".mp3"
    else:
        temp_base = os.path.join(task_work_dir, f"dl_{task_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(m3u8_url, timeout=10)
                total_frags = len([line for line in response.text.splitlines() if line.strip() and not line.startswith("#")])
        except Exception as exc:
            log_debug(f"Failed to get total fragments: {exc}")

        success = await download_stream_with_ytdlp(m3u8_url, temp_base, total_frags, progress_callback)
        if not success:
            raise ProcessingError("Stream download failed or timed out.")

        await progress_callback(100.0, total_frags, total_frags, phase="downloading")

        for extension in [".mp4", ".m4a", ".mp3"]:
            candidate = temp_base + extension
            if os.path.exists(candidate):
                source = candidate
                source_ext = extension
                break

    cover_path = await download_cover_artifact(cover_url, task_work_dir, title_base)

    try:
        if not source:
            raise ProcessingError("Download pipeline finished without producing an output file.")

        final_file = ""
        final_source_path = ""

        if mode == "zip" and chapters:
            await report_assembly_progress(0.0, 0, len(chapters))
            final_source_path = await build_zip_from_chapters(
                source, chapters, title_base, task_id, task_work_dir, source_ext, report_assembly_progress
            )
            final_file = f"{title_base}.zip"
        elif mode == "m4b" and chapters:
            await report_assembly_progress(0.0, 0, 100)
            final_source_path = await build_m4b_with_chapters(
                source,
                chapters,
                title_base,
                task_id,
                task_work_dir,
                cover_path,
                lambda pct: report_assembly_progress(pct, round(pct), 100),
            )
            final_file = f"{title_base}.m4b"
        else:
            final_file = f"{title_base}{source_ext}"
            final_source_path = source

        if not final_source_path or not os.path.exists(final_source_path):
            if mode == "m4b" and chapters:
                raise ProcessingError("Failed to assemble the final M4B file.")
            if mode == "zip" and chapters:
                raise ProcessingError("Failed to split the book into ZIP chapters.")
            raise ProcessingError("Final media artifact was not created.")

        moved_final_path = move_to_library(final_source_path, final_file)
        if not moved_final_path:
            raise ProcessingError("Failed to move the finished book into the library.")
        if os.path.exists(source) and os.path.abspath(source) != os.path.abspath(final_source_path):
            os.remove(source)

        try:
            staged_meta_json_path = os.path.join(task_work_dir, f"{title_base}.json")
            meta_data = {
                "title": title_base,
                "mode": mode,
                "file_name": final_file,
                "chapters": chapters,
                "source_url": source_url,
                "cover_url": cover_url,
                "local_cover": os.path.basename(cover_path) if cover_path else None,
            }
            async with aiofiles.open(staged_meta_json_path, "w", encoding="utf-8") as handle:
                await handle.write(json.dumps(meta_data, ensure_ascii=False, indent=2))
            move_to_library(staged_meta_json_path, f"{title_base}.json")
        except Exception as exc:
            log_debug(f"Failed to write metadata JSON: {exc}")

        if cover_path and os.path.exists(cover_path):
            move_to_library(cover_path, os.path.basename(cover_path))

        shutil.rmtree(task_work_dir, ignore_errors=True)
        return final_file
    except Exception as exc:
        log_debug(f"Final assembly error: {exc}")
        if isinstance(exc, ProcessingError):
            raise
        raise ProcessingError("Final assembly step failed.") from exc
