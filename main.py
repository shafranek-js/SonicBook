import os
import asyncio
import sys
import uvicorn
import re
import uuid
import string
import datetime
import httpx
import subprocess
import shutil
import zipfile
import json
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

app = FastAPI(title="SonicBook API")
DOWNLOADS_DIR = "downloads"
DEBUG_LOG = "app_debug.log"

# ВОЗВРАЩАЕМ ПОЛНЫЕ ПУТИ ДЛЯ ВАШЕЙ СИСТЕМЫ
FFMPEG_PATH = r"C:\Users\pavel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.WinGet.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\Users\pavel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.WinGet.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffprobe.exe"

if not os.path.exists(DOWNLOADS_DIR): os.makedirs(DOWNLOADS_DIR)

def log_debug(message):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f: f.write(f"[{ts}] {message}\n")
    except: pass
    print(f"DEBUG: {message}")

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    mode: str = "m4b"

progress_store = {}

def parse_time_to_seconds(value: str) -> int:
    try:
        parts = value.split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except: pass
    return 0

def sanitize_filename(name):
    if not name or len(name.strip()) < 2: return f"audiobook_{str(uuid.uuid4())[:8]}"
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars)
    return " ".join(cleaned.split()).strip(". ")[:100]

async def get_stream_duration(m3u8_url):
    try:
        cmd = [FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", m3u8_url]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return float(stdout.decode().strip())
    except: return 0

def extract_chapters_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text("\n", strip=True)
    start_marker, end_marker = "Список глав", "Скрыть главы"
    if start_marker in text and end_marker in text:
        text = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tracks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m_first = re.match(r"^\d{2}:\d{2}\s*/\s*((?:\d{2}:)?\d{2}:\d{2})$", line)
        if m_first:
            duration = m_first.group(1)
            j = i + 1
            while j < len(lines):
                candidate = lines[j]
                if candidate in {"15 c", "1x", "100%", "Скорость", "Главы", "Список глав", "Закрыть"}: j += 1; continue
                if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", candidate): break
                tracks.append({"duration": duration, "title": candidate.strip()}); i = j; break
            i += 1; continue
        if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", line):
            duration = line
            j = i + 1
            while j < len(lines):
                candidate = lines[j]
                if not candidate or candidate in {"15 c", "1x", "100%", "Скорость"}: j += 1; continue
                if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", candidate) or candidate.isdigit(): break
                tracks.append({"duration": duration, "title": candidate.strip()}); i = j; break
        i += 1
    chapters = []; current_start = 0
    for t in tracks:
        dur_sec = parse_time_to_seconds(t["duration"])
        chapters.append({"title": t["title"], "start": current_start, "end": current_start + dur_sec})
        current_start += dur_sec
    return chapters

async def get_book_info(book_url):
    log_debug(f"Combined info scraping: {book_url}")
    res = {"m3u8": None, "title": "audiobook", "chapters": []}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(book_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                h1 = soup.find("h1")
                if h1: res["title"] = h1.get_text().strip()
                res["chapters"] = extract_chapters_from_html(resp.text)
    except Exception as e: log_debug(f"Text parse error: {e}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,ico,css}", lambda route: route.abort())
            page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)
            await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)
            if not res["m3u8"]:
                try: await page.click(".js-player-play", timeout=2000); await asyncio.sleep(3)
                except: pass
            await browser.close()
    except Exception as e: log_debug(f"Playwright error: {e}")
    return res["m3u8"], sanitize_filename(res["title"]), res["chapters"]

async def create_m4b_with_chapters(source_file, chapters, title_base, task_id):
    log_debug(f"M4B assembly for {title_base}...")
    meta_path = os.path.join(DOWNLOADS_DIR, f"meta_{task_id}.txt")
    meta_content = ";FFMETADATA1\ntitle=" + title_base + "\n"
    for ch in chapters:
        s, e = int(ch['start'] * 1000), int(ch['end'] * 1000)
        meta_content += f"\n[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={ch['title']}\n"
    with open(meta_path, "w", encoding="utf-8") as f: f.write(meta_content)
    final_filename = f"{title_base}.m4b"
    final_path = os.path.join(DOWNLOADS_DIR, final_filename)
    cmd = [FFMPEG_PATH, "-y", "-i", source_file, "-i", meta_path, "-map_metadata", "1", "-c:a", "copy", final_path]
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await p.wait()
    if os.path.exists(meta_path): os.remove(meta_path)
    return final_filename

async def split_to_chapters(source_file, chapters, title_base, task_id):
    temp_dir = os.path.join(DOWNLOADS_DIR, f"split_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)
    split_files = []
    for i, ch in enumerate(chapters):
        ch_title = sanitize_filename(f"{i+1:03d} - {ch['title']}")
        out = os.path.join(temp_dir, f"{ch_title}.mp3")
        dur = ch['end'] - ch['start']
        if dur <= 0: continue
        cmd = [FFMPEG_PATH, "-y", "-ss", str(ch['start']), "-t", str(dur), "-i", source_file, "-c:a", "libmp3lame", "-b:a", "128k", out]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await p.wait()
        split_files.append(out)
    if not split_files: return None
    zip_name = f"{title_base}.zip"
    zip_path = os.path.join(DOWNLOADS_DIR, zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in split_files: z.write(f, os.path.basename(f))
    shutil.rmtree(temp_dir)
    return zip_name

async def run_fast_download(task_id, m3u8_url, title_base, chapters, mode):
    temp_base = os.path.join(DOWNLOADS_DIR, f"temp_{task_id}")
    total_dur = await get_stream_duration(m3u8_url)
    total_frags = 0
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(m3u8_url, timeout=10)
            total_frags = len([l for l in r.text.splitlines() if l.strip() and not l.startswith('#')])
    except: pass
    progress_store[task_id]["total_frags"] = total_frags

    command = [sys.executable, "-m", "yt_dlp", m3u8_url, "-o", f"{temp_base}.%(ext)s", "--concurrent-fragments", "16", "--ffmpeg-location", FFMPEG_PATH, "--newline", "--no-colors"]
    
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
                fm = re.search(r"Got fragment\s*(\d+)", line, re.I)
                if fm:
                    curr = int(fm.group(1)); progress_store[task_id]["current_frag"] = curr
                    if total_frags > 0: progress_store[task_id]["percent"] = round((curr / total_frags) * 95.0, 3)
                tm = re.search(r"time=\s*(\d+:\d+:\d+[\.\d]*)", line, re.I)
                if tm and total_dur > 0:
                    p = tm.group(1).split(':')
                    curr_t = float(p[0]) * 3600 + float(p[1]) * 60 + float(p[2])
                    pct = round((curr_t / total_dur) * 95.0, 3)
                    progress_store[task_id]["percent"] = min(95.0, pct)
                    if total_frags > 0: progress_store[task_id]["current_frag"] = int(total_frags * (pct / 95))

        progress_store[task_id]["status"] = "merging"
        await process.wait()
        
        source = ""
        for ext in ['.mp4', '.m4a', '.mp3']:
            if os.path.exists(temp_base + ext): source = temp_base + ext; break
        
        if source:
            final_file = ""
            if mode == "zip" and chapters: final_file = await split_to_chapters(source, chapters, title_base, task_id)
            elif mode == "m4b" and chapters: final_file = await create_m4b_with_chapters(source, chapters, title_base, task_id)
            elif mode == "mp3":
                final_file = f"{title_base}.mp3"
                dest = os.path.join(DOWNLOADS_DIR, final_file)
                cmd = [FFMPEG_PATH, "-y", "-i", source, "-c:a", "libmp3lame", "-b:a", "128k", dest]
                p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await p.wait()
            else:
                ext = os.path.splitext(source)[1]
                final_file = f"{title_base}{ext}"
                dest = os.path.join(DOWNLOADS_DIR, final_file)
                if os.path.exists(dest): os.remove(dest)
                os.rename(source, dest)
            if os.path.exists(source): os.remove(source)
            progress_store[task_id].update({"status": "success", "percent": 100.0, "file_name": final_file})
        else: progress_store[task_id]["status"] = "error"
    except Exception as e:
        log_debug(f"Crash in download: {e}")
        progress_store[task_id]["status"] = "error"

@app.get("/", response_class=HTMLResponse)
async def read_item():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.post("/api/info")
async def get_info(request: InfoRequest):
    m3u8, title, chapters = await get_book_info(request.url)
    if not m3u8: raise HTTPException(status_code=404, detail="Stream not found")
    return {"title": title, "chapters": chapters}

@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    progress_store[task_id] = {"status": "searching", "percent": 0.0, "current_frag": 0, "total_frags": 0, "file_name": ""}
    background_tasks.add_task(process_task, task_id, request.url, request.mode)
    return {"task_id": task_id}

async def process_task(task_id, url, mode):
    m3u8, title, chapters = await get_book_info(url)
    if not m3u8: progress_store[task_id]["status"] = "error"; return
    progress_store[task_id].update({"status": "processing"})
    await run_fast_download(task_id, m3u8, title, chapters, mode)

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str): return progress_store.get(task_id, {"status": "not_found"})

@app.get("/api/files/{file_name}")
async def get_file(file_name: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(DOWNLOADS_DIR, file_name)
    if os.path.exists(file_path):
        background_tasks.add_task(os.remove, file_path)
        return FileResponse(path=file_path, filename=file_name)
    raise HTTPException(status_code=404)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
