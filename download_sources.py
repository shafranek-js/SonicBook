import asyncio
import logging
import os
import re
import shutil

import aiofiles
import httpx

import config

logger = logging.getLogger(__name__)
_HOST_SEMAPHORES = {}
_HOST_SEMAPHORES_LOCK = asyncio.Lock()


def log_debug(message):
    logger.info(message)


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


async def get_host_semaphore(url):
    from urllib.parse import urlparse

    host = (urlparse(url).netloc or "").lower()
    if not host:
        return asyncio.Semaphore(1)
    async with _HOST_SEMAPHORES_LOCK:
        semaphore = _HOST_SEMAPHORES.get(host)
        if semaphore is None:
            semaphore = asyncio.Semaphore(config.MULTI_CONNECTION_MAX_SEGMENTS)
            _HOST_SEMAPHORES[host] = semaphore
        return semaphore


async def probe_multi_connection_download(url):
    try:
        async with httpx.AsyncClient(http2=False, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"Range": "bytes=0-0"},
                timeout=httpx.Timeout(15.0, read=30.0),
            )
            if response.status_code != 206:
                return 0
            content_range = parse_content_range_header(response.headers.get("content-range"))
            if not content_range or not content_range["total"]:
                return 0
            return int(content_range["total"])
    except (httpx.HTTPError, ValueError) as e:
        log_debug(f"Multi-connection probe failed, using single stream: {e}")
        return 0


def build_byte_ranges(total_bytes, segments):
    segment_count = max(1, min(int(segments), int(total_bytes)))
    base_size = total_bytes // segment_count
    ranges = []
    start = 0
    for index in range(segment_count):
        end = total_bytes - 1 if index == segment_count - 1 else start + base_size - 1
        ranges.append((start, end))
        start = end + 1
    return ranges


async def download_direct_urls(urls, temp_dir, task_id, progress_callback):
    """Download direct MP3 chapter URLs with bounded concurrency and resume retries."""
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
                    async with client.stream("GET", url, headers=headers, timeout=httpx.Timeout(30.0, read=120.0)) as response:
                        if resume_offset > 0 and response.status_code == 200:
                            log_debug(f"Chunk {index}: server ignored Range resume from {resume_offset}, restarting from zero")
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            await asyncio.sleep(1)
                            continue
                        if response.status_code == 416:
                            log_debug(f"Chunk {index}: server rejected Range resume from {resume_offset}, restarting from zero")
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
                        async with aiofiles.open(file_path, open_mode) as f:
                            async for chunk in response.aiter_bytes(1024 * 256):
                                if not chunk:
                                    continue
                                wrote_bytes += len(chunk)
                                await f.write(chunk)

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
                except (httpx.HTTPError, OSError, ValueError) as e:
                    partial_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    if partial_size <= 0 and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
                    if partial_size > 0:
                        log_debug(
                            f"Chunk {index} failed (attempt {attempt+1}/{retries}), keeping {partial_size} bytes for resume: {e}"
                        )
                    else:
                        log_debug(f"Chunk {index} failed (attempt {attempt+1}/{retries}): {e}")
                    await asyncio.sleep(min(10, 2 * (attempt + 1)))

        log_debug(f"Failed to download {url} after {retries} attempts.")
        return None

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=2), http2=False, follow_redirects=True) as client:
        tasks = [download_file(client, url, i) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)

    valid_files = [f for f in results if f]

    if len(valid_files) < len(urls) * 0.5:
        log_debug("Too many failed chunks, aborting merge.")
        return None

    list_file = os.path.join(temp_dir, "concat_list.txt")
    async with aiofiles.open(list_file, "w", encoding="utf-8") as f:
        for vf in valid_files:
            safe_path = vf.replace("\\", "/")
            await f.write(f"file '{safe_path}'\n")

    merged_file = os.path.join(os.path.dirname(temp_dir), f"merged_{task_id}.mp3")
    cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file,
        "-c",
        "copy",
        merged_file,
    ]
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await p.wait()

    shutil.rmtree(temp_dir)
    return merged_file


async def _download_single_file_stream(url, dest_path, progress_callback):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    async with httpx.AsyncClient(http2=False, follow_redirects=True) as client:
        async with client.stream("GET", url, timeout=httpx.Timeout(30.0, read=300.0)) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("content-length") or 0)
            downloaded_bytes = 0
            async with aiofiles.open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(1024 * 256):
                    if not chunk:
                        continue
                    downloaded_bytes += len(chunk)
                    await f.write(chunk)
                    percent = round((downloaded_bytes / total_bytes) * 100.0, 3) if total_bytes > 0 else 0.0
                    await progress_callback(percent, downloaded_bytes, total_bytes, phase="downloading")

            if total_bytes > 0 and downloaded_bytes < total_bytes:
                raise RuntimeError(f"Download incomplete: got {downloaded_bytes} of {total_bytes} bytes")

    return dest_path if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0 else None


async def _download_single_file_multi_connection(url, dest_path, total_bytes, progress_callback):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    segment_count = min(
        config.MULTI_CONNECTION_MAX_SEGMENTS,
        max(2, total_bytes // config.MULTI_CONNECTION_MIN_BYTES),
    )
    ranges = build_byte_ranges(total_bytes, segment_count)
    part_paths = [f"{dest_path}.part{index}" for index in range(len(ranges))]
    temp_dest_path = f"{dest_path}.multi"
    downloaded_bytes = 0
    progress_lock = asyncio.Lock()
    host_semaphore = await get_host_semaphore(url)

    async def report_progress(delta):
        nonlocal downloaded_bytes
        async with progress_lock:
            downloaded_bytes += delta
            percent = round((downloaded_bytes / total_bytes) * 100.0, 3) if total_bytes > 0 else 0.0
            await progress_callback(percent, downloaded_bytes, total_bytes, phase="downloading")

    async def download_part(client, index, start, end):
        expected_size = end - start + 1
        part_path = part_paths[index]
        async with host_semaphore:
            async with client.stream(
                "GET",
                url,
                headers={"Range": f"bytes={start}-{end}"},
                timeout=httpx.Timeout(30.0, read=300.0),
            ) as response:
                if response.status_code != 206:
                    raise RuntimeError(f"Range request returned HTTP {response.status_code}")
                content_range = parse_content_range_header(response.headers.get("content-range"))
                if not content_range or content_range["start"] != start or content_range["end"] != end:
                    raise RuntimeError(f"Unexpected Content-Range: {response.headers.get('content-range')}")

                part_bytes = 0
                async with aiofiles.open(part_path, "wb") as f:
                    async for chunk in response.aiter_bytes(1024 * 256):
                        if not chunk:
                            continue
                        part_bytes += len(chunk)
                        await f.write(chunk)
                        await report_progress(len(chunk))

        if part_bytes != expected_size:
            raise RuntimeError(f"Incomplete range part {index}: got {part_bytes}, expected {expected_size}")

    try:
        for path in [*part_paths, temp_dest_path]:
            if os.path.exists(path):
                os.remove(path)

        async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=len(ranges)),
            http2=False,
            follow_redirects=True,
        ) as client:
            results = await asyncio.gather(
                *[
                    download_part(client, index, start, end)
                    for index, (start, end) in enumerate(ranges)
                ],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise RuntimeError(f"Range segment download failed: {result}") from result

        async with aiofiles.open(temp_dest_path, "wb") as dest_file:
            for part_path in part_paths:
                async with aiofiles.open(part_path, "rb") as part_file:
                    while True:
                        chunk = await part_file.read(1024 * 1024)
                        if not chunk:
                            break
                        await dest_file.write(chunk)

        if os.path.getsize(temp_dest_path) != total_bytes:
            raise RuntimeError(f"Combined file size mismatch: got {os.path.getsize(temp_dest_path)}, expected {total_bytes}")

        os.replace(temp_dest_path, dest_path)
        await progress_callback(100.0, total_bytes, total_bytes, phase="downloading")
        log_debug(f"Multi-connection download completed with {len(ranges)} segments: {dest_path}")
        return dest_path
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as e:
        log_debug(f"Multi-connection download failed, falling back to single stream: {e}")
        return None
    finally:
        for path in [*part_paths, temp_dest_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


async def download_single_file(url, dest_path, progress_callback):
    if config.MULTI_CONNECTION_DOWNLOADS:
        total_bytes = await probe_multi_connection_download(url)
        if total_bytes >= config.MULTI_CONNECTION_MIN_BYTES:
            result = await _download_single_file_multi_connection(url, dest_path, total_bytes, progress_callback)
            if result:
                return result

    return await _download_single_file_stream(url, dest_path, progress_callback)


async def _handle_direct_urls_download(m3u8_url, task_work_dir, task_id, progress_callback):
    urls = m3u8_url.replace("DIRECT_URLS:", "").split(",")
    temp_dir = os.path.join(task_work_dir, "direct-download")
    source = await download_direct_urls(urls, temp_dir, task_id, progress_callback)
    if not source:
        return None, None
    return source, ".mp3"


async def _handle_direct_zip_download(m3u8_url, task_work_dir, task_id, progress_callback):
    zip_url = m3u8_url.replace("DIRECT_ZIP:", "", 1).strip()
    source = await download_single_file(zip_url, os.path.join(task_work_dir, f"dl_{task_id}.zip"), progress_callback)
    if not source:
        return None, None
    return source, ".zip"


async def _handle_ytdlp_download(m3u8_url, task_work_dir, task_id, progress_callback):
    temp_base = os.path.join(task_work_dir, f"dl_{task_id}")
    total_frags = 0

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(m3u8_url, timeout=10)
            total_frags = len([line for line in r.text.splitlines() if line.strip() and not line.startswith("#")])
    except httpx.HTTPError as e:
        log_debug(f"Failed to get total fragments: {e}")

    current_loop = asyncio.get_running_loop()

    def download_with_ytdlp():
        import time

        import yt_dlp
        from yt_dlp.utils import DownloadError, ExtractorError

        last_update_time = 0

        def progress_hook(d):
            nonlocal last_update_time

            if d["status"] == "downloading":
                now = time.time()
                if now - last_update_time < 0.5:
                    return
                last_update_time = now

                percent = None
                curr_frag = None
                total = total_frags

                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total_bytes > 0 and d.get("downloaded_bytes"):
                    percent = round((d["downloaded_bytes"] / total_bytes) * 100.0, 3)

                if percent is None and "_percent_str" in d:
                    try:
                        match = re.search(r"([0-9]+\.[0-9]+|[0-9]+)", d["_percent_str"])
                        if match:
                            percent = min(100.0, float(match.group(1)))
                    except (AttributeError, TypeError, ValueError) as e:
                        log_debug(f"Percent string parse error: {e}")

                if "fragment_index" in d and "fragment_count" in d:
                    curr_frag = d.get("fragment_index", 0)
                    total = d.get("fragment_count", total_frags)

                if percent is not None or curr_frag is not None:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            progress_callback(percent, curr_frag, total, phase="downloading"),
                            current_loop,
                        )
                    except RuntimeError as e:
                        log_debug(f"Failed to schedule yt-dlp progress update: {e}")

        ydl_opts = {
            "outtmpl": f"{temp_base}.%(ext)s",
            "concurrent_fragment_downloads": config.YTDLP_CONCURRENCY,
            "ffmpeg_location": config.FFMPEG_PATH,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "cachedir": False,
            "progress_hooks": [progress_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([m3u8_url])
            return True
        except (DownloadError, ExtractorError, OSError, RuntimeError):
            logger.exception("yt-dlp Python API error for %s", m3u8_url)
            return False

    try:
        success = await asyncio.wait_for(current_loop.run_in_executor(None, download_with_ytdlp), timeout=14400)
    except asyncio.TimeoutError:
        log_debug(f"yt-dlp download timeout (4 hours) for {task_id}")
        success = False

    if not success:
        return None, None

    await progress_callback(100.0, total_frags, total_frags, phase="downloading")

    for ext in [".mp4", ".m4a", ".mp3"]:
        if os.path.exists(temp_base + ext):
            return temp_base + ext, ext

    return None, None
