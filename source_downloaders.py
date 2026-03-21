import asyncio
import os
import re
import shutil
import time

import aiofiles
import httpx

import config
from media_helpers import log_debug, parse_content_range_header


async def download_direct_urls(urls, temp_dir, task_id, progress_callback):
    os.makedirs(temp_dir, exist_ok=True)
    total_files = len(urls)
    downloaded = 0
    semaphore = asyncio.Semaphore(2)

    async def download_file(client, url, index, retries=5):
        nonlocal downloaded
        file_path = os.path.join(temp_dir, f"{index:04d}.mp3")

        async with semaphore:
            for attempt in range(retries):
                resume_offset = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                headers = {"Range": f"bytes={resume_offset}-"} if resume_offset > 0 else {}
                try:
                    async with client.stream(
                        "GET", url, headers=headers, timeout=httpx.Timeout(30.0, read=120.0)
                    ) as response:
                        if resume_offset > 0 and response.status_code == 200:
                            log_debug(
                                f"Chunk {index}: server ignored Range resume from {resume_offset}, restarting from zero"
                            )
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            await asyncio.sleep(1)
                            continue
                        if response.status_code == 416:
                            log_debug(
                                f"Chunk {index}: server rejected Range resume from {resume_offset}, restarting from zero"
                            )
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            await asyncio.sleep(1)
                            continue

                        response.raise_for_status()

                        content_range = parse_content_range_header(response.headers.get("content-range"))
                        content_length = int(response.headers.get("content-length") or 0)
                        open_mode = "wb"
                        expected_total = None

                        if resume_offset > 0 and response.status_code == 206:
                            if not content_range or content_range["start"] != resume_offset:
                                raise ValueError(
                                    f"Unexpected Content-Range for resumed chunk: {response.headers.get('content-range')}"
                                )
                            open_mode = "ab"
                            expected_total = content_range["total"]
                            log_debug(f"Resuming chunk {index} from {resume_offset} bytes")
                        else:
                            if resume_offset > 0 and os.path.exists(file_path):
                                os.remove(file_path)
                                resume_offset = 0
                            expected_total = content_range["total"] if content_range else (content_length or None)

                        wrote_bytes = 0
                        async with aiofiles.open(file_path, open_mode) as handle:
                            async for chunk in response.aiter_bytes(1024 * 256):
                                if not chunk:
                                    continue
                                wrote_bytes += len(chunk)
                                await handle.write(chunk)

                    final_size = os.path.getsize(file_path)
                    if final_size <= 0:
                        raise ValueError("Downloaded direct-url file is empty")
                    if wrote_bytes <= 0 and resume_offset <= 0:
                        raise ValueError("Direct-url response body produced no bytes")
                    if expected_total is not None and final_size < expected_total:
                        raise ValueError(
                            f"Incomplete direct-url file: have {final_size} bytes, expected {expected_total}"
                        )

                    downloaded += 1
                    percent = round((downloaded / total_files) * 100.0, 3)
                    log_debug(f"Direct chunk {index} saved ({final_size} bytes)")
                    await progress_callback(percent, downloaded, total_files, phase="downloading")
                    return file_path
                except Exception as exc:
                    partial_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    if partial_size <= 0 and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
                    if partial_size > 0:
                        log_debug(
                            f"Chunk {index} failed (attempt {attempt + 1}/{retries}), keeping {partial_size} bytes for resume: {exc}"
                        )
                    else:
                        log_debug(f"Chunk {index} failed (attempt {attempt + 1}/{retries}): {exc}")
                    await asyncio.sleep(min(10, 2 * (attempt + 1)))

        log_debug(f"Failed to download {url} after {retries} attempts.")
        return None

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=2), http2=False, follow_redirects=True) as client:
        tasks = [download_file(client, url, index) for index, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)

    valid_files = [file_path for file_path in results if file_path]
    if len(valid_files) < len(urls) * 0.5:
        log_debug("Too many failed chunks, aborting merge.")
        return None

    list_file = os.path.join(temp_dir, "concat_list.txt")
    async with aiofiles.open(list_file, "w", encoding="utf-8") as handle:
        for file_path in valid_files:
            safe_path = file_path.replace("\\", "/")
            await handle.write(f"file '{safe_path}'\n")

    merged_file = os.path.join(os.path.dirname(temp_dir), f"merged_{task_id}.mp3")
    cmd = [config.FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", merged_file]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await process.wait()

    shutil.rmtree(temp_dir)
    return merged_file


async def download_stream_with_ytdlp(m3u8_url, temp_base, total_frags, progress_callback):
    current_loop = asyncio.get_running_loop()

    def download_with_ytdlp():
        import yt_dlp

        last_update_time = 0

        def progress_hook(data):
            nonlocal last_update_time

            if data["status"] != "downloading":
                return

            now = time.time()
            if now - last_update_time < 0.5:
                return
            last_update_time = now

            percent = None
            current_fragment = None
            total = total_frags

            total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total_bytes > 0 and data.get("downloaded_bytes"):
                percent = round((data["downloaded_bytes"] / total_bytes) * 100.0, 3)

            if percent is None and "_percent_str" in data:
                try:
                    match = re.search(r"([0-9]+\.[0-9]+|[0-9]+)", data["_percent_str"])
                    if match:
                        percent = min(100.0, float(match.group(1)))
                except Exception as exc:
                    log_debug(f"Percent string parse error: {exc}")

            if "fragment_index" in data and "fragment_count" in data:
                current_fragment = data.get("fragment_index", 0)
                total = data.get("fragment_count", total_frags)

            if percent is not None or current_fragment is not None:
                try:
                    asyncio.run_coroutine_threadsafe(
                        progress_callback(percent, current_fragment, total, phase="downloading"),
                        current_loop,
                    )
                except Exception:
                    pass

        ydl_opts = {
            "outtmpl": f"{temp_base}.%(ext)s",
            "concurrent_fragment_downloads": 16,
            "ffmpeg_location": config.FFMPEG_PATH,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [progress_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([m3u8_url])
            return True
        except Exception as exc:
            log_debug(f"yt-dlp Python API error for {m3u8_url}: {exc}")
            return False

    try:
        return await asyncio.wait_for(current_loop.run_in_executor(None, download_with_ytdlp), timeout=14400)
    except asyncio.TimeoutError:
        log_debug(f"yt-dlp download timeout (4 hours) for {temp_base}")
        return False
