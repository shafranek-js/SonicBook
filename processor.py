import os
import asyncio
import sys
import re
import zipfile
import shutil
import httpx
import config

def log_debug(message):
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(config.DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except: pass
    print(f"DEBUG: {message}")

async def get_stream_duration(m3u8_url):
    try:
        cmd = [config.FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", m3u8_url]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except: return 0

def sanitize_filename(name):
    import string
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars)
    return " ".join(cleaned.split()).strip(". ")[:100]

async def create_m4b_with_chapters(source_file, chapters, title_base, task_id):
    """Исправлено: Использование нейтральных имен для FFmpeg во избежание ошибок кодировки"""
    log_debug(f"M4B assembly for task {task_id}...")
    meta_path = os.path.join(config.DOWNLOADS_DIR, f"meta_{task_id}.txt")
    
    meta_content = ";FFMETADATA1\ntitle=" + title_base + "\n"
    for ch in chapters:
        s, e = int(ch['start'] * 1000), int(ch['end'] * 1000)
        meta_content += f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={ch['title']}\n"
    
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(meta_content)
    
    # Нейтральное имя для сборки
    temp_m4b = os.path.join(config.DOWNLOADS_DIR, f"out_{task_id}.m4b")
    
    cmd = [
        config.FFMPEG_PATH, "-y", "-i", source_file, "-i", meta_path,
        "-map_metadata", "1", "-c:a", "copy", temp_m4b
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await process.wait()
    
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
                    with open(file_path, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
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
    with open(list_file, "w", encoding="utf-8") as f:
        for vf in valid_files:
            safe_path = vf.replace('\\', '/')
            f.write(f"file '{safe_path}'\n")
            
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
        # СТАНДАРТНАЯ ЗАГРУЗКА ЧЕРЕЗ YT-DLP
        temp_base = os.path.join(config.DOWNLOADS_DIR, f"dl_{task_id}")
        total_dur = await get_stream_duration(m3u8_url)
        
        total_frags = 0
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(m3u8_url, timeout=10)
                total_frags = len([l for l in r.text.splitlines() if l.strip() and not l.startswith('#')])
        except: pass

        command = [
            sys.executable, "-m", "yt_dlp", m3u8_url, "-o", f"{temp_base}.%(ext)s",
            "--concurrent-fragments", "16", "--ffmpeg-location", config.FFMPEG_PATH,
            "--newline", "--no-colors"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            buffer = ""
            while True:
                chunk = await process.stdout.read(1024)
                if not chunk: break
                buffer += chunk.decode(errors='replace')
                while "\n" in buffer or "\r" in buffer:
                    m = re.search(r"[\n\r]", buffer); line = buffer[:m.start()].strip(); buffer = buffer[m.end():]
                    if not line: continue
                    
                    curr_frag = None
                    percent = None
                    
                    fm = re.search(r"Got fragment\s*(\d+)", line, re.I)
                    if fm:
                        curr_frag = int(fm.group(1))
                        if total_frags > 0: percent = round((curr_frag / total_frags) * 95.0, 3)
                    
                    tm = re.search(r"time=\s*(\d+:\d+:\d+[\.\d]*)", line, re.I)
                    if tm and total_dur > 0:
                        p = tm.group(1).split(':')
                        curr_t = float(p[0]) * 3600 + float(p[1]) * 60 + float(p[2])
                        percent = min(95.0, round((curr_t / total_dur) * 95.0, 3))
                        if total_frags > 0: curr_frag = int(total_frags * (percent / 95))
                    
                    if percent is not None or curr_frag is not None:
                        await progress_callback(percent, curr_frag, total_frags)

            await process.wait()
            
            source = ""; source_ext = ""
            for ext in ['.mp4', '.m4a', '.mp3']:
                if os.path.exists(temp_base + ext): source = temp_base + ext; source_ext = ext; break
        except Exception as e:
            log_debug(f"yt-dlp Process error: {e}")
            return None

    # ФИНАЛЬНАЯ СБОРКА И НАРЕЗКА (ОБЩАЯ ДЛЯ ОБОИХ МЕТОДОВ)
    try:
        if source:
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
            return final_file
        return None
    except Exception as e:
        log_debug(f"Final assembly error: {e}")
        return None
