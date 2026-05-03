import os
import asyncio
import zipfile
import shutil
import logging
import aiofiles
import config
from download_sources import (
    _handle_direct_urls_download,
    _handle_direct_zip_download,
    _handle_ytdlp_download,
    download_direct_urls,
    download_single_file,
    parse_content_range_header,
)
from ffmpeg_helpers import get_media_duration, get_stream_duration, parse_ffmpeg_out_time, run_ffmpeg_with_progress
from library_finalization import validate_zip_file, write_metadata_sidecar
from library_storage import move_to_library, prepare_task_work_dir
from media_assembly import create_m4b_with_chapters as _create_m4b_with_chapters
from media_assembly import split_to_chapters
from media_assets import download_cover
from media_helpers import resolve_cover_extension, sanitize_filename

logger = logging.getLogger(__name__)

def log_debug(message):
    logger.info(message)

async def create_m4b_with_chapters(source_file, chapters, title_base, task_id, work_dir, cover_path=None, progress_callback=None):
    return await _create_m4b_with_chapters(
        source_file,
        chapters,
        title_base,
        task_id,
        work_dir,
        cover_path,
        progress_callback,
        get_media_duration_fn=get_media_duration,
        run_ffmpeg_with_progress_fn=run_ffmpeg_with_progress,
    )

async def run_fast_download(task_id, m3u8_url, title_base, chapters, mode, progress_callback, cover_url=None, source_url=None):
    task_work_dir = prepare_task_work_dir(task_id)
    source = ""
    source_ext = ""
    cover_path = None

    async def report_assembly_progress(percent, current=None, total=None):
        await progress_callback(percent, current, total, status="assembling", phase="assembling")

    if m3u8_url.startswith("DIRECT_URLS:"):
        source, source_ext = await _handle_direct_urls_download(m3u8_url, task_work_dir, task_id, progress_callback)
    elif m3u8_url.startswith("DIRECT_ZIP:"):
        source, source_ext = await _handle_direct_zip_download(m3u8_url, task_work_dir, task_id, progress_callback)
    else:
        source, source_ext = await _handle_ytdlp_download(m3u8_url, task_work_dir, task_id, progress_callback)

    if not source:
        return None

    cover_path = await download_cover(cover_url, task_work_dir, title_base)

    # ФИНАЛЬНАЯ СБОРКА И НАРЕЗКА (ОБЩАЯ ДЛЯ ОБОИХ МЕТОДОВ)
    try:
        if source:
            final_file = ""
            final_source_path = ""
            assembled_with_progress = False
            if mode == "zip" and chapters:
                await report_assembly_progress(0.0, 0, len(chapters))
                final_source_path = await split_to_chapters(source, chapters, title_base, task_id, task_work_dir, source_ext, report_assembly_progress)
                final_file = f"{title_base}.zip"
                assembled_with_progress = True
            elif mode == "m4b" and chapters:
                await report_assembly_progress(0.0, 0, 100)
                final_source_path = await create_m4b_with_chapters(source, chapters, title_base, task_id, task_work_dir, cover_path, lambda pct: report_assembly_progress(pct, round(pct), 100))
                final_file = f"{title_base}.m4b"
                assembled_with_progress = True
            else:
                final_file = f"{title_base}{source_ext}"
                final_source_path = source

            if not final_source_path or not os.path.exists(final_source_path):
                return None

            # Валидация ZIP-файла перед переносом в библиотеку
            if final_file.lower().endswith(".zip"):
                await asyncio.to_thread(validate_zip_file, final_source_path)

            post_steps_total = 2 + (1 if cover_path and os.path.exists(cover_path) else 0)
            post_steps_done = 0
            if not assembled_with_progress:
                await progress_callback(100.0, post_steps_done, post_steps_total, status="merging", phase="downloading")

            moved_final_path = await asyncio.to_thread(move_to_library, final_source_path, final_file)
            if not moved_final_path:
                return None
            post_steps_done += 1
            if not assembled_with_progress:
                await progress_callback(100.0, post_steps_done, post_steps_total, status="merging", phase="downloading")
            if os.path.exists(source) and os.path.abspath(source) != os.path.abspath(final_source_path):
                os.remove(source)

            # Generate JSON metadata for the integrated web player
            await write_metadata_sidecar(
                task_work_dir,
                title_base,
                final_file,
                chapters,
                source_ext,
                mode,
                move_to_library,
                source_url=source_url,
                cover_url=cover_url,
                cover_path=cover_path,
            )
            post_steps_done += 1
            if not assembled_with_progress:
                await progress_callback(100.0, post_steps_done, post_steps_total, status="merging", phase="downloading")

            if cover_path and os.path.exists(cover_path):
                await asyncio.to_thread(move_to_library, cover_path, os.path.basename(cover_path))
                post_steps_done += 1
                if not assembled_with_progress:
                    await progress_callback(100.0, post_steps_done, post_steps_total, status="merging", phase="downloading")

            shutil.rmtree(task_work_dir, ignore_errors=True)

            return final_file
        return None
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as e:
        log_debug(f"Final assembly error: {e}")
        if isinstance(e, RuntimeError):
            raise
        return None
