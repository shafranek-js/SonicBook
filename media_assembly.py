import asyncio
import logging
import os
import shutil
import zipfile

import aiofiles

import config
from ffmpeg_helpers import get_media_duration, run_ffmpeg_with_progress
from media_helpers import sanitize_filename

logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


async def create_m4b_with_chapters(
    source_file,
    chapters,
    title_base,
    task_id,
    work_dir,
    cover_path=None,
    progress_callback=None,
    get_media_duration_fn=None,
    run_ffmpeg_with_progress_fn=None,
):
    """Assemble an M4B with chapter metadata using neutral temporary filenames."""
    get_duration = get_media_duration_fn or get_media_duration
    run_ffmpeg = run_ffmpeg_with_progress_fn or run_ffmpeg_with_progress

    log_debug(f"M4B assembly for task {task_id}...")
    meta_path = os.path.join(work_dir, f"meta_{task_id}.txt")

    meta_content = ";FFMETADATA1\ntitle=" + title_base + "\n"
    for ch in chapters:
        s = int(ch["start"] * 1000)
        e = int(ch["end"] * 1000)

        if e <= s:
            e = s + 1000

        meta_content += f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={ch['title']}\n"

    async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
        await f.write(meta_content)

    temp_m4b = os.path.join(work_dir, f"out_{task_id}.m4b")

    source_ext = os.path.splitext(source_file)[1].lower()
    needs_audio_transcode = source_ext == ".mp3"

    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-progress",
        "pipe:1",
        "-nostats",
        "-i",
        source_file,
        "-i",
        meta_path,
    ]

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

    source_duration = await get_duration(source_file)
    returncode, stderr, timed_out = await run_ffmpeg(cmd, source_duration, progress_callback, timeout=3600)
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


async def split_to_chapters(source_file, chapters, title_base, task_id, work_dir, source_ext, progress_callback=None):
    log_debug(f"Fast splitting into {len(chapters)} files...")
    temp_dir = os.path.join(work_dir, f"split_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)

    split_files = []
    ext = source_ext if source_ext != ".mp4" else ".m4a"

    for i, ch in enumerate(chapters):
        temp_out = os.path.join(temp_dir, f"ch_{i}{ext}")
        dur = ch["end"] - ch["start"]
        if dur <= 0:
            continue

        cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-ss",
            str(ch["start"]),
            "-t",
            str(dur),
            "-i",
            source_file,
            "-c",
            "copy",
            temp_out,
        ]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(p.wait(), timeout=600)
        except asyncio.TimeoutError:
            p.kill()
            log_debug(f"FFmpeg timeout (10 mins) splitting chapter {i}")
            continue

        nice_name = sanitize_filename(f"{i+1:03d} - {ch['title']}") + ext
        nice_path = os.path.join(temp_dir, nice_name)
        if os.path.exists(temp_out):
            os.rename(temp_out, nice_path)
            split_files.append(nice_path)
            if progress_callback is not None:
                percent = round(((i + 1) / len(chapters)) * 100.0, 3)
                await progress_callback(percent, i + 1, len(chapters))

    zip_name = f"{title_base}.zip"
    zip_path = os.path.join(work_dir, zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in split_files:
            z.write(f, os.path.basename(f))
    if progress_callback is not None and chapters:
        await progress_callback(100.0, len(chapters), len(chapters))
    shutil.rmtree(temp_dir)
    return zip_path
