import asyncio
import logging
import os
import re
import shutil
import string
from urllib.parse import urlparse

import config


logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


def parse_ffmpeg_out_time(value):
    try:
        hours, minutes, seconds = value.strip().split(":")
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    except Exception:
        return 0.0


def parse_content_range_header(value):
    match = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", (value or "").strip(), re.IGNORECASE)
    if not match:
        return None
    start, end, total = match.groups()
    return {
        "start": int(start),
        "end": int(end),
        "total": None if total == "*" else int(total),
    }


async def get_stream_duration(m3u8_url):
    try:
        cmd = [
            config.FFPROBE_PATH,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            m3u8_url,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except Exception as exc:
        log_debug(f"Failed to get stream duration: {exc}")
        return 0


async def get_media_duration(media_path):
    try:
        cmd = [
            config.FFPROBE_PATH,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except Exception as exc:
        log_debug(f"Failed to get media duration for {media_path}: {exc}")
        return 0


async def run_ffmpeg_with_progress(cmd, duration_seconds, progress_callback=None, timeout=3600):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_chunks = []

    async def read_progress():
        last_reported = -1.0
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace").strip()
            if not text:
                continue
            if text.startswith("out_time=") and duration_seconds > 0 and progress_callback is not None:
                out_seconds = parse_ffmpeg_out_time(text.split("=", 1)[1])
                percent = max(0.0, min(100.0, round((out_seconds / duration_seconds) * 100.0, 3)))
                if percent > last_reported:
                    last_reported = percent
                    await progress_callback(percent)

    async def read_stderr():
        while True:
            chunk = await process.stderr.read(8192)
            if not chunk:
                break
            stderr_chunks.append(chunk)

    try:
        await asyncio.wait_for(asyncio.gather(read_progress(), read_stderr(), process.wait()), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return None, b"".join(stderr_chunks), True

    return process.returncode, b"".join(stderr_chunks), False


def sanitize_filename(name):
    valid_chars = (
        f"-_.() {string.ascii_letters}{string.digits}"
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    )
    cleaned = "".join(c for c in name if c in valid_chars and c != ",")
    return " ".join(cleaned.split()).strip(". ")[:100]


def resolve_cover_extension(cover_url, content_type):
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"

    url_ext = os.path.splitext(urlparse(cover_url).path)[1].lower()
    if url_ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if url_ext == ".jpeg" else url_ext

    return ".jpg"


def prepare_task_work_dir(task_id):
    task_dir = os.path.join(config.WORK_DIR, task_id)
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir, ignore_errors=True)
    os.makedirs(task_dir, exist_ok=True)
    return task_dir


def move_to_library(src_path, dest_name):
    if not src_path or not os.path.exists(src_path):
        return None
    if os.path.isfile(src_path) and os.path.getsize(src_path) <= 0:
        log_debug(f"Refusing to move empty artifact into library: {src_path}")
        return None

    dest_path = os.path.join(config.DOWNLOADS_DIR, dest_name)
    if os.path.exists(dest_path):
        if os.path.isdir(dest_path):
            shutil.rmtree(dest_path)
        else:
            os.remove(dest_path)
    return shutil.move(src_path, dest_path)
