import asyncio
import os
import shutil
import zipfile

import aiofiles
import httpx

import config
from media_helpers import (
    get_media_duration,
    log_debug,
    resolve_cover_extension,
    run_ffmpeg_with_progress,
    sanitize_filename,
)


async def download_cover_artifact(cover_url, task_work_dir, title_base):
    if not cover_url:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(cover_url, follow_redirects=True, timeout=30)
            if response.status_code == 200 and response.headers.get("content-type", "").lower().startswith("image/"):
                extension = resolve_cover_extension(cover_url, response.headers.get("content-type"))
                cover_path = os.path.join(task_work_dir, f"{title_base}{extension}")
                async with aiofiles.open(cover_path, "wb") as handle:
                    await handle.write(response.content)
                return cover_path
    except Exception as exc:
        log_debug(f"Failed to download cover: {exc}")
    return None


async def build_m4b_with_chapters(source_file, chapters, title_base, task_id, work_dir, cover_path=None, progress_callback=None):
    log_debug(f"M4B assembly for task {task_id}...")
    meta_path = os.path.join(work_dir, f"meta_{task_id}.txt")

    meta_content = ";FFMETADATA1\ntitle=" + title_base + "\n"
    for chapter in chapters:
        start_ms = int(chapter["start"] * 1000)
        end_ms = int(chapter["end"] * 1000)
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        meta_content += (
            f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_ms}\nEND={end_ms}\n"
            f"title={chapter['title']}\n"
        )

    async with aiofiles.open(meta_path, "w", encoding="utf-8") as handle:
        await handle.write(meta_content)

    temp_m4b = os.path.join(work_dir, f"out_{task_id}.m4b")
    source_ext = os.path.splitext(source_file)[1].lower()
    needs_audio_transcode = source_ext == ".mp3"

    cmd = [config.FFMPEG_PATH, "-y", "-progress", "pipe:1", "-nostats", "-i", source_file, "-i", meta_path]

    if cover_path and os.path.exists(cover_path):
        cmd.extend(["-i", cover_path, "-map", "0:a", "-map", "2:v"])
        if needs_audio_transcode:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-c:a", "copy"])
        cmd.extend(["-c:v", "copy", "-disposition:v", "attached_pic"])
    else:
        cmd.extend(["-map", "0:a"])
        if needs_audio_transcode:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-c:a", "copy"])

    cmd.extend(["-map_metadata", "1", temp_m4b])

    source_duration = await get_media_duration(source_file)
    returncode, stderr, timed_out = await run_ffmpeg_with_progress(
        cmd, source_duration, progress_callback, timeout=3600
    )
    if timed_out:
        log_debug(f"FFmpeg timeout (1 hour) assembling M4B for {task_id}")
        return None

    if returncode != 0:
        log_debug(f"FFmpeg Error (code {returncode}): {stderr.decode(errors='replace')}")

    if os.path.exists(meta_path):
        os.remove(meta_path)

    if returncode == 0 and os.path.exists(temp_m4b) and os.path.getsize(temp_m4b) > 0:
        return temp_m4b

    if os.path.exists(temp_m4b):
        try:
            os.remove(temp_m4b)
        except OSError:
            pass
    return None


async def build_zip_from_chapters(source_file, chapters, title_base, task_id, work_dir, source_ext, progress_callback=None):
    log_debug(f"Fast splitting into {len(chapters)} files...")
    temp_dir = os.path.join(work_dir, f"split_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)

    split_files = []
    extension = source_ext if source_ext != ".mp4" else ".m4a"

    for index, chapter in enumerate(chapters):
        temp_out = os.path.join(temp_dir, f"ch_{index}{extension}")
        duration = chapter["end"] - chapter["start"]
        if duration <= 0:
            continue

        cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-ss",
            str(chapter["start"]),
            "-t",
            str(duration),
            "-i",
            source_file,
            "-c",
            "copy",
            temp_out,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=600)
        except asyncio.TimeoutError:
            process.kill()
            log_debug(f"FFmpeg timeout (10 mins) splitting chapter {index}")
            continue

        nice_name = sanitize_filename(f"{index + 1:03d} - {chapter['title']}") + extension
        nice_path = os.path.join(temp_dir, nice_name)
        if os.path.exists(temp_out):
            os.rename(temp_out, nice_path)
            split_files.append(nice_path)
            if progress_callback is not None:
                percent = round(((index + 1) / len(chapters)) * 100.0, 3)
                await progress_callback(percent, index + 1, len(chapters))

    zip_path = os.path.join(work_dir, f"{title_base}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in split_files:
            archive.write(file_path, os.path.basename(file_path))

    if progress_callback is not None and chapters:
        await progress_callback(100.0, len(chapters), len(chapters))
    shutil.rmtree(temp_dir)
    return zip_path
