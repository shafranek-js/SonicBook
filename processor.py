import os
import asyncio
import sys
import re
import zipfile
import shutil
import logging
import aiofiles
import httpx
import config

logger = logging.getLogger(__name__)

def log_debug(message):
    logger.info(message)

async def get_stream_duration(m3u8_url):
    try:
        cmd = [config.FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", m3u8_url]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except Exception as e:
        log_debug(f"Failed to get stream duration: {e}")
        return 0

def sanitize_filename(name):
    import string
    # Remove commas and other potential problematic chars for shell/ffmpeg
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars and c != ',')
    return " ".join(cleaned.split()).strip(". ")[:100]

async def create_m4b_with_chapters(source_file, chapters, title_base, task_id):
    """Исправлено: Использование нейтральных имен для FFmpeg во избежание ошибок кодировки"""
    log_debug(f"M4B assembly for task {task_id}...")
    meta_path = os.path.join(config.DOWNLOADS_DIR, f"meta_{task_id}.txt")
    
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
    temp_m4b = os.path.join(config.DOWNLOADS_DIR, f"out_{task_id}.m4b")
    
    cmd = [
        config.FFMPEG_PATH, "-y", "-i", source_file, "-i", meta_path,
        "-map_metadata", "1", "-c:a", "copy", temp_m4b
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        log_debug(f"FFmpeg Error (code {process.returncode}): {stderr.decode(errors='replace')}")
    
    if os.path.exists(meta_path): os.remove(meta_path)
    
    # Переименовываем в красивое название после сборки
    final_filename = f"{title_base}.m4b"
    final_path = os.path.join(config.DOWNLOADS_DIR, final_filename)
    
    if os.path.exists(temp_m4b):
        if os.path.exists(final_path): os.remove(final_path)
        os.rename(temp_m4b, final_path)
        return final_filename
    return None

async def split_to_chapters(source_file, chapters, title_base, task_id, source_ext):
    log_debug(f"Fast splitting into {len(chapters)} files...")
    temp_dir = os.path.join(config.DOWNLOADS_DIR, f"split_{task_id}")
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
        await p.wait()
        
        # Переименовываем в красивое название средствами Python
        nice_name = sanitize_filename(f"{i+1:03d} - {ch['title']}") + ext
        nice_path = os.path.join(temp_dir, nice_name)
        if os.path.exists(temp_out):
            os.rename(temp_out, nice_path)
            split_files.append(nice_path)
    
    zip_name = f"{title_base}.zip"
    zip_path = os.path.join(config.DOWNLOADS_DIR, zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in split_files:
            z.write(f, os.path.basename(f))
    shutil.rmtree(temp_dir)
    return zip_name

async def download_direct_urls(urls, temp_dir, task_id, progress_callback):
    """Кастомный параллельный загрузчик для прямых MP3 ссылок с защитой от обрывов"""
    os.makedirs(temp_dir, exist_ok=True)
    total_files = len(urls)
    downloaded = 0
    
    async def download_file(client, url, index, retries=3):
        nonlocal downloaded
        file_path = os.path.join(temp_dir, f"{index:04d}.mp3")
        
        for attempt in range(retries):
            try:
                # Используем увеличенные таймауты
                async with client.stream('GET', url, timeout=httpx.Timeout(30.0, read=120.0)) as response:
                    response.raise_for_status()
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            await f.write(chunk)
                downloaded += 1
                percent = round((downloaded / total_files) * 95.0, 3)
                await progress_callback(percent, downloaded, total_files)
                return file_path
            except Exception as e:
                log_debug(f"Chunk {index} failed (attempt {attempt+1}/{retries}): {e}")
                await asyncio.sleep(2) # Пауза перед новой попыткой
        
        log_debug(f"Failed to download {url} after {retries} attempts.")
        return None

    # Скачиваем в 4 потока, чтобы не перегружать сервер и избежать обрывов (peer closed connection)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=4), http2=True) as client:
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
    merged_file = os.path.join(config.DOWNLOADS_DIR, f"merged_{task_id}.mp3")
    cmd = [
        config.FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", merged_file
    ]
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await p.wait()
    
    # Убираем мусор
    shutil.rmtree(temp_dir)
    return merged_file

async def run_fast_download(task_id, m3u8_url, title_base, chapters, mode, progress_callback):
    # ПРОВЕРКА НА ПРЯМЫЕ ССЫЛКИ
    if m3u8_url.startswith("DIRECT_URLS:"):
        urls = m3u8_url.replace("DIRECT_URLS:", "").split(",")
        temp_dir = os.path.join(config.DOWNLOADS_DIR, f"dl_dir_{task_id}")
        source = await download_direct_urls(urls, temp_dir, task_id, progress_callback)
        if not source: return None
        source_ext = ".mp3"
    else:
        # СТАНДАРТНАЯ ЗАГРУЗКА ЧЕРЕЗ YT-DLP API
        temp_base = os.path.join(config.DOWNLOADS_DIR, f"dl_{task_id}")
        
        # Получаем общее количество фрагментов, если это возможно, для fallback-расчетов
        total_frags = 0
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(m3u8_url, timeout=10)
                total_frags = len([l for l in r.text.splitlines() if l.strip() and not l.startswith('#')])
        except Exception as e:
            log_debug(f"Failed to get total fragments: {e}")

        # Запускаем синхронный yt-dlp в отдельном потоке (executor), чтобы не заблокировать сервер
        current_loop = asyncio.get_running_loop()

        # Создаем обертку для синхронного yt-dlp, чтобы не блокировать event loop
        def download_with_ytdlp():
            import yt_dlp
            import time
            
            last_update_time = 0
            
            def progress_hook(d):
                nonlocal last_update_time
                
                if d['status'] == 'downloading':
                    now = time.time()
                    # Обновляем не чаще 2 раз в секунду, чтобы не заспамить event loop
                    if now - last_update_time < 0.5:
                        return
                    last_update_time = now
                    
                    percent = None
                    curr_frag = None
                    total = total_frags
                    
                    # Пытаемся получить прогресс по байтам (самый точный метод)
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    if total_bytes > 0 and d.get('downloaded_bytes'):
                        percent = round((d['downloaded_bytes'] / total_bytes) * 95.0, 3)
                    
                    # Fallback на парсинг строки процентов (убираем ~, ANSI-коды и прочий мусор)
                    if percent is None and '_percent_str' in d:
                        try:
                            match = re.search(r'([0-9]+\.[0-9]+|[0-9]+)', d['_percent_str'])
                            if match:
                                percent = min(95.0, float(match.group(1)) * 0.95)
                        except Exception as e:
                            log_debug(f"Percent string parse error: {e}")

                    # Количество фрагментов
                    if 'fragment_index' in d and 'fragment_count' in d:
                        curr_frag = d.get('fragment_index', 0)
                        total = d.get('fragment_count', total_frags)
                    
                    # Отправляем прогресс обратно в асинхронный event loop
                    if percent is not None or curr_frag is not None:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                progress_callback(percent, curr_frag, total), 
                                current_loop
                            )
                        except Exception as e:
                            pass

            ydl_opts = {
                'outtmpl': f"{temp_base}.%(ext)s",
                'concurrent_fragment_downloads': 16,
                'ffmpeg_location': config.FFMPEG_PATH,
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [progress_hook],
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([m3u8_url])
                return True
            except Exception as e:
                log_debug(f"yt-dlp Python API error: {e}")
                return False

        success = await current_loop.run_in_executor(None, download_with_ytdlp)
        
        if not success:
            return None
            
        source = ""; source_ext = ""
        for ext in ['.mp4', '.m4a', '.mp3']:
            if os.path.exists(temp_base + ext): 
                source = temp_base + ext
                source_ext = ext
                break

    # ФИНАЛЬНАЯ СБОРКА И НАРЕЗКА (ОБЩАЯ ДЛЯ ОБОИХ МЕТОДОВ)
    try:
        if source:
            await progress_callback(100.0, total_frags, total_frags, status="assembling")
            
            final_file = ""
            if mode == "zip" and chapters:
                final_file = await split_to_chapters(source, chapters, title_base, task_id, source_ext)
            elif mode == "m4b" and chapters:
                final_file = await create_m4b_with_chapters(source, chapters, title_base, task_id)
            else:
                final_file = f"{title_base}{source_ext}"
                dest = os.path.join(config.DOWNLOADS_DIR, final_file)
                if os.path.exists(dest): os.remove(dest)
                os.rename(source, dest)
            
            if os.path.exists(source): os.remove(source)

            # Generate JSON metadata for the integrated web player
            try:
                import json
                meta_json_path = os.path.join(config.DOWNLOADS_DIR, f"{title_base}.json")
                meta_data = {
                    "title": title_base,
                    "mode": mode,
                    "file_name": final_file,
                    "chapters": chapters
                }
                async with aiofiles.open(meta_json_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(meta_data, ensure_ascii=False, indent=2))
            except Exception as meta_e:
                log_debug(f"Failed to write metadata JSON: {meta_e}")

            return final_file
        return None
    except Exception as e:
        log_debug(f"Final assembly error: {e}")
        return None
