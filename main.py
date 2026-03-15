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
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright

# Windows subprocess fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

app = FastAPI(title="SonicBook API")
DOWNLOADS_DIR = "downloads"
DEBUG_LOG = "app_debug.log"

# Названия команд теперь системные (предполагается, что они в PATH)
FFMPEG_CMD = "ffmpeg"
FFPROBE_CMD = "ffprobe"

if not os.path.exists(DOWNLOADS_DIR): os.makedirs(DOWNLOADS_DIR)

def log_debug(message):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f: f.write(f"[{ts}] {message}\n")
    except: pass
    print(f"DEBUG: {message}")

progress_store = {}

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    split_chapters: bool = False

def sanitize_filename(name):
    if not name or len(name.strip()) < 2: return f"audiobook_{str(uuid.uuid4())[:8]}"
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars)
    return " ".join(cleaned.split()).strip(". ")[:100]

async def get_stream_duration(m3u8_url):
    try:
        cmd = [FFPROBE_CMD, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", m3u8_url]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
            return float(stdout.decode().strip())
        except: return 0
    except: return 0

async def get_book_info(book_url):
    log_debug(f"SonicBook Scraper: {book_url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,css}", lambda route: route.abort())
            
            res = {"m3u8": None, "title": "audiobook", "chapters": []}
            page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)
            
            try:
                await page.goto(book_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(2)
                
                h1 = await page.query_selector("h1")
                if h1:
                    raw_title = (await h1.inner_text()).strip()
                    res["title"] = re.sub(r"\s*\(?аудиокнига\)?.*$", "", raw_title, flags=re.I).strip()
                
                author = await page.query_selector("a.link__author")
                if author:
                    a_text = (await author.inner_text()).strip()
                    if a_text and a_text not in res["title"]: res["title"] = f"{a_text} - {res['title']}"

                play_btn = page.locator(".js-player-play").first
                if await play_btn.is_visible():
                    await play_btn.click()
                    await asyncio.sleep(5)

                res["chapters"] = await page.evaluate("""() => {
                    let data = window.items || window.playlist || (window.audioPlayer ? window.audioPlayer.playlist : null);
                    if (data && Array.isArray(data) && data.length > 0) {
                        return data.map(i => ({title: i.title, start: i.time_from_start, end: i.time_finish}));
                    }
                    return [];
                }""")
            except Exception as e:
                log_debug(f"Scraper sub-error: {e}")

            await browser.close()
            return res["m3u8"], sanitize_filename(res["title"]), res["chapters"]
    except Exception as e:
        log_debug(f"Scraper critical: {e}")
        return None, "audiobook", []

async def split_to_chapters(source_file, chapters, title_base, task_id):
    temp_dir = os.path.join(DOWNLOADS_DIR, f"split_{task_id}")
    os.makedirs(temp_dir, exist_ok=True)
    split_files = []
    for i, ch in enumerate(chapters):
        ch_title = sanitize_filename(f"{i+1:03d} - {ch['title']}")
        output_path = os.path.join(temp_dir, f"{ch_title}.mp3")
        dur = ch['end'] - ch['start']
        if dur <= 0: continue
        cmd = [FFMPEG_CMD, "-y", "-ss", str(ch['start']), "-t", str(dur), "-i", source_file, "-c", "copy", output_path]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await p.wait()
        split_files.append(output_path)

    if not split_files: return None
    zip_name = f"{title_base}.zip"
    zip_path = os.path.join(DOWNLOADS_DIR, zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in split_files: z.write(f, os.path.basename(f))
    shutil.rmtree(temp_dir)
    return zip_name

async def run_fast_download(task_id, m3u8_url, title_base, chapters, should_split):
    temp_base = os.path.join(DOWNLOADS_DIR, f"temp_{task_id}")
    total_dur = await get_stream_duration(m3u8_url)
    total_frags = 0
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(m3u8_url, timeout=15)
            total_frags = len([l for l in r.text.splitlines() if l.strip() and not l.startswith('#')])
    except: pass
    progress_store[task_id]["total_frags"] = total_frags

    command = [
        sys.executable, "-m", "yt_dlp", m3u8_url,
        "-o", f"{temp_base}.%(ext)s",
        "--concurrent-fragments", "16",
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
                m = re.search(r"[\n\r]", buffer)
                line = buffer[:m.start()].strip()
                buffer = buffer[m.end():]
                if not line: continue
                
                fm = re.search(r"Got fragment\s*(\d+)", line, re.I)
                if fm:
                    curr = int(fm.group(1))
                    progress_store[task_id]["current_frag"] = curr
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
            if should_split and chapters and len(chapters) > 1:
                zip_file = await split_to_chapters(source, chapters, title_base, task_id)
                if zip_file:
                    os.remove(source)
                    progress_store[task_id].update({"status": "success", "percent": 100.0, "file_name": zip_file})
                    return
            ext = os.path.splitext(source)[1]
            final_name = f"{title_base}{ext}"
            dest = os.path.join(DOWNLOADS_DIR, final_name)
            if os.path.exists(dest): os.remove(dest)
            os.rename(source, dest)
            progress_store[task_id].update({"status": "success", "percent": 100.0, "file_name": final_name})
        else: progress_store[task_id]["status"] = "error"
    except Exception as e:
        log_debug(f"Process error: {e}")
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
    background_tasks.add_task(process_task, task_id, request.url, request.split_chapters)
    return {"task_id": task_id}

async def process_task(task_id, url, should_split):
    m3u8, title, chapters = await get_book_info(url)
    if not m3u8:
        progress_store[task_id]["status"] = "error"
        return
    progress_store[task_id].update({"status": "processing"})
    await run_fast_download(task_id, m3u8, title, chapters, should_split)

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
