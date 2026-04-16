import os
import asyncio
import sys
import re
import zipfile
import shutil
import logging
import aiofiles
import httpx
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
        "total": None if total == "*" else int(total)
    }

async def get_stream_duration(m3u8_url):
    try:
        cmd = [config.FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", m3u8_url]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except Exception as e:
        log_debug(f"Failed to get stream duration: {e}")
        return 0

async def get_media_duration(media_path):
    try:
        cmd = [config.FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", media_path]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except Exception as e:
        log_debug(f"Failed to get media duration for {media_path}: {e}")
        return 0

async def run_ffmpeg_with_progress(cmd, duration_seconds, progress_callback=None, timeout=3600):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
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
    import string
    # Remove commas and other potential problematic chars for shell/ffmpeg
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars and c != ',')
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

async def create_m4b_with_chapters(source_file, chapters, title_base, task_id, work_dir, cover_path=None, progress_callback=None):
    """Исправлено: Использование нейтральных имен для FFmpeg во избежание ошибок кодировки"""
    log_debug(f"M4B assembly for task {task_id}...")
    meta_path = os.path.join(work_dir, f"meta_{task_id}.txt")
    
    meta_content = ";FFMETADATA1\ntitle=" + title_base + "\n"
    for i, ch in enumerate(chapters):
        s = int(ch['start'] * 1000)
        e = int(ch['end'] * 1000)
        
        # FFmpeg requirement: END must be greater than START
        if e <= s:
            e = s + 1000 # Default to 1 second if end is missing or invalid
            
        meta_content += f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={ch['title']}\n"
    
    async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
        await f.write(meta_content)
    
    # Нейтральное имя для сборки
    temp_m4b = os.path.join(work_dir, f"out_{task_id}.m4b")
    
    source_ext = os.path.splitext(source_file)[1].lower()
    needs_audio_transcode = source_ext == ".mp3"

    cmd = [
        config.FFMPEG_PATH, "-y", "-progress", "pipe:1", "-nostats", "-i", source_file, "-i", meta_path
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
    
    source_duration = await get_media_duration(source_file)
    returncode, stderr, timed_out = await run_ffmpeg_with_progress(cmd, source_duration, progress_callback, timeout=3600)
    if timed_out:
        log_debug(f"FFmpeg timeout (1 hour) assembling M4B for {task_id}")
        return None
    
    if returncode != 0:
        log_debug(f"FFmpeg Error (code {returncode}): {stderr.decode(errors='replace')}")
    
    if os.path.exists(meta_path): os.remove(meta_path)

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
    ext = source_ext if source_ext != '.mp4' else '.m4a'
    
    for i, ch in enumerate(chapters):
        # Используем индекс для временного файла, чтобы избежать проблем с кодировкой в ffmpeg
        temp_out = os.path.join(temp_dir, f"ch_{i}{ext}")
        dur = ch['end'] - ch['start']
        if dur <= 0: continue
        
        cmd = [config.FFMPEG_PATH, "-y", "-ss", str(ch['start']), "-t", str(dur), "-i", source_file, "-c", "copy", temp_out]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(p.wait(), timeout=600)
        except asyncio.TimeoutError:
            p.kill()
            log_debug(f"FFmpeg timeout (10 mins) splitting chapter {i}")
            continue
        
        # Переименовываем в красивое название средствами Python
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
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in split_files:
            z.write(f, os.path.basename(f))
    if progress_callback is not None and chapters:
        await progress_callback(100.0, len(chapters), len(chapters))
    shutil.rmtree(temp_dir)
    return zip_path

async def download_direct_urls(urls, temp_dir, task_id, progress_callback):
    """Кастомный параллельный загрузчик для прямых MP3 ссылок с resume-повторами."""
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
                        open_mode = 'wb'
                        expected_total = None

                        if resume_offset > 0 and response.status_code == 206:
                            if not content_range or content_range["start"] != resume_offset:
                                raise ValueError(
                                    f"Unexpected Content-Range for resumed chunk: {response.headers.get('content-range')}"
                                )
                            open_mode = 'ab'
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
                except Exception as e:
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
    
    # Отфильтруем неудачные
    valid_files = [f for f in results if f]
    
    # Если скачалось меньше половины - считаем загрузку неудачной
    if len(valid_files) < len(urls) * 0.5:
        log_debug("Too many failed chunks, aborting merge.")
        return None
    
    # Создаем файл списка для ffmpeg concat
    list_file = os.path.join(temp_dir, "concat_list.txt")
    async with aiofiles.open(list_file, "w", encoding="utf-8") as f:
        for vf in valid_files:
            safe_path = vf.replace('\\', '/')
            await f.write(f"file '{safe_path}'\n")
            
    # Склеиваем всё в один файл
    merged_file = os.path.join(os.path.dirname(temp_dir), f"merged_{task_id}.mp3")
    cmd = [
        config.FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", merged_file
    ]
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await p.wait()
    
    # Убираем мусор
    shutil.rmtree(temp_dir)
    return merged_file


async def download_single_file(url, dest_path, progress_callback):
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
            total_frags = len([l for l in r.text.splitlines() if l.strip() and not l.startswith('#')])
    except Exception as e:
        log_debug(f"Failed to get total fragments: {e}")

    current_loop = asyncio.get_running_loop()

    def download_with_ytdlp():
        import yt_dlp
        import time

        last_update_time = 0

        def progress_hook(d):
            nonlocal last_update_time

            if d['status'] == 'downloading':
                now = time.time()
                if now - last_update_time < 0.5:
                    return
                last_update_time = now

                percent = None
                curr_frag = None
                total = total_frags

                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                if total_bytes > 0 and d.get('downloaded_bytes'):
                    percent = round((d['downloaded_bytes'] / total_bytes) * 100.0, 3)

                if percent is None and '_percent_str' in d:
                    try:
                        match = re.search(r'([0-9]+\.[0-9]+|[0-9]+)', d['_percent_str'])
                        if match:
                            percent = min(100.0, float(match.group(1)))
                    except Exception as e:
                        log_debug(f"Percent string parse error: {e}")

                if 'fragment_index' in d and 'fragment_count' in d:
                    curr_frag = d.get('fragment_index', 0)
                    total = d.get('fragment_count', total_frags)

                if percent is not None or curr_frag is not None:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            progress_callback(percent, curr_frag, total, phase="downloading"),
                            current_loop
                        )
                    except Exception as e:
                        pass

        ydl_opts = {
            'outtmpl': f"{temp_base}.%(ext)s",
            'concurrent_fragment_downloads': config.YTDLP_CONCURRENCY,
            'ffmpeg_location': config.FFMPEG_PATH,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'cachedir': False,
            'progress_hooks': [progress_hook],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([m3u8_url])
            return True
        except Exception as e:
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

    for ext in ['.mp4', '.m4a', '.mp3']:
        if os.path.exists(temp_base + ext):
            return temp_base + ext, ext
            
    return None, None

async def _download_source(m3u8_url, task_work_dir, task_id, progress_callback):
    if m3u8_url.startswith("DIRECT_URLS:"):
        return await _handle_direct_urls_download(m3u8_url, task_work_dir, task_id, progress_callback)
    elif m3u8_url.startswith("DIRECT_ZIP:"):
        return await _handle_direct_zip_download(m3u8_url, task_work_dir, task_id, progress_callback)
    else:
        return await _handle_ytdlp_download(m3u8_url, task_work_dir, task_id, progress_callback)

async def _download_cover(cover_url, task_work_dir, title_base):
    if not cover_url:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(cover_url, follow_redirects=True, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("image/"):
                c_ext = resolve_cover_extension(cover_url, r.headers.get("content-type"))
                cover_path = os.path.join(task_work_dir, f"{title_base}{c_ext}")
                async with aiofiles.open(cover_path, 'wb') as f:
                    await f.write(r.content)
                return cover_path
            else:
                return None
    except Exception as e:
        log_debug(f"Failed to download cover: {e}")
        return None

async def run_fast_download(task_id, m3u8_url, title_base, chapters, mode, progress_callback, cover_url=None, source_url=None):
    task_work_dir = prepare_task_work_dir(task_id)
    source = ""
    source_ext = ""
    cover_path = None

    async def report_assembly_progress(percent, current=None, total=None):
        await progress_callback(percent, current, total, status="assembling", phase="assembling")

    source, source_ext = await _download_source(m3u8_url, task_work_dir, task_id, progress_callback)

    if not source:
        return None

    # Download cover if provided
    cover_path = await _download_cover(cover_url, task_work_dir, title_base)

    # ФИНАЛЬНАЯ СБОРКА И НАРЕЗКА (ОБЩАЯ ДЛЯ ОБОИХ МЕТОДОВ)
    return await _assemble_and_postprocess(source, source_ext, title_base, chapters, mode, task_id, task_work_dir, cover_path, cover_url, source_url, progress_callback, report_assembly_progress)

def _validate_zip(path):
    import zipfile
    if not zipfile.is_zipfile(path):
        raise RuntimeError("Downloaded ZIP file is corrupted or not a valid archive")
    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip() is not None:
                raise RuntimeError("Downloaded ZIP file contains broken files")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"ZIP validation failed: {e}")

async def _write_metadata_json(task_work_dir, title_base, effective_mode, final_file, chapters, source_url, cover_url, cover_path):
    try:
        import json
        staged_meta_json_path = os.path.join(task_work_dir, f"{title_base}.json")
        meta_data = {
            "title": title_base,
            "mode": effective_mode,
            "file_name": final_file,
            "chapters": chapters,
            "source_url": source_url,
            "cover_url": cover_url,
            "local_cover": os.path.basename(cover_path) if cover_path else None
        }
        async with aiofiles.open(staged_meta_json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta_data, ensure_ascii=False, indent=2))
        await asyncio.to_thread(move_to_library, staged_meta_json_path, f"{title_base}.json")
    except Exception as meta_e:
        log_debug(f"Failed to write metadata JSON: {meta_e}")

async def _assemble_and_postprocess(source, source_ext, title_base, chapters, mode, task_id, task_work_dir, cover_path, cover_url, source_url, progress_callback, report_assembly_progress):
    try:
        if not source:
            return None

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
            await asyncio.to_thread(_validate_zip, final_source_path)

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
        effective_mode = "zip" if source_ext == ".zip" or final_file.lower().endswith(".zip") else mode
        await _write_metadata_json(task_work_dir, title_base, effective_mode, final_file, chapters, source_url, cover_url, cover_path)
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
    except Exception as e:
        log_debug(f"Final assembly error: {e}")
        if isinstance(e, RuntimeError):
            raise
        return None
