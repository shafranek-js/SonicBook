import asyncio
import json
import logging
import os
import zipfile

import aiofiles

logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


def validate_zip_file(path):
    if not zipfile.is_zipfile(path):
        raise RuntimeError("Downloaded ZIP file is corrupted or not a valid archive")
    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip() is not None:
                raise RuntimeError("Downloaded ZIP file contains broken files")
    except RuntimeError:
        raise
    except (OSError, zipfile.BadZipFile) as e:
        raise RuntimeError(f"ZIP validation failed: {e}") from e


def build_metadata_payload(title_base, final_file, chapters, source_ext, mode, source_url=None, cover_url=None, cover_path=None):
    effective_mode = "zip" if source_ext == ".zip" or final_file.lower().endswith(".zip") else mode
    return {
        "title": title_base,
        "mode": effective_mode,
        "file_name": final_file,
        "chapters": chapters,
        "source_url": source_url,
        "cover_url": cover_url,
        "local_cover": os.path.basename(cover_path) if cover_path else None,
    }


async def write_metadata_sidecar(
    task_work_dir,
    title_base,
    final_file,
    chapters,
    source_ext,
    mode,
    move_to_library_fn,
    source_url=None,
    cover_url=None,
    cover_path=None,
):
    try:
        staged_meta_json_path = os.path.join(task_work_dir, f"{title_base}.json")
        meta_data = build_metadata_payload(
            title_base,
            final_file,
            chapters,
            source_ext,
            mode,
            source_url=source_url,
            cover_url=cover_url,
            cover_path=cover_path,
        )
        async with aiofiles.open(staged_meta_json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta_data, ensure_ascii=False, indent=2))
        await asyncio.to_thread(move_to_library_fn, staged_meta_json_path, f"{title_base}.json")
        return True
    except (OSError, TypeError, ValueError) as e:
        log_debug(f"Failed to write metadata JSON: {e}")
        return False
