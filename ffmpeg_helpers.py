import asyncio
import logging

import config

logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


def parse_ffmpeg_out_time(value):
    try:
        val_str = value.strip()
        is_negative = val_str.startswith("-")
        if is_negative:
            val_str = val_str[1:]

        hours, minutes, seconds = val_str.split(":")
        total_seconds = (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)

        return -total_seconds if is_negative else total_seconds
    except (AttributeError, TypeError, ValueError):
        return 0.0


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
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except (asyncio.TimeoutError, OSError, ValueError) as e:
        log_debug(f"Failed to get stream duration: {e}")
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
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except (asyncio.TimeoutError, OSError, ValueError) as e:
        log_debug(f"Failed to get media duration for {media_path}: {e}")
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
