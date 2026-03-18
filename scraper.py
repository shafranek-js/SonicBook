import re
import asyncio
import json
import logging
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import config
from processor import sanitize_filename

logger = logging.getLogger(__name__)

def log_debug(message):
    logger.info(message)

# Persistent Playwright browser instance
playwright_instance = None
browser_instance = None

async def init_browser():
    global playwright_instance, browser_instance
    if not playwright_instance:
        log_debug("Initializing persistent Playwright browser...")
        playwright_instance = await async_playwright().start()
        browser_instance = await playwright_instance.chromium.launch(headless=True)

async def close_browser():
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()
    playwright_instance = None
    browser_instance = None

def parse_time_to_seconds(time_str):
    try:
        parts = value.split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except: pass
    return 0

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
                if candidate in {"15 c", "1x", "100%", "Скорость", "Главы", "Список глав", "Закрыть"}: 
                    j += 1; continue
                if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", candidate): break
                title = candidate.strip()
                # ФИЛЬТРАЦИЯ: пропускаем строки, состоящие только из знаков препинания
                if title and not re.match(r"^[/\s\-\.,_]+$", title):
                    tracks.append({"duration": duration, "title": title})
                    i = j; break
                j += 1
            i += 1; continue
        if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", line):
            duration = line
            j = i + 1
            while j < len(lines):
                candidate = lines[j]
                if not candidate or candidate in {"15 c", "1x", "100%", "Скорость"}: 
                    j += 1; continue
                if re.match(r"^(?:\d{2}:)?\d{2}:\d{2}$", candidate) or candidate.isdigit(): break
                title = candidate.strip()
                # ФИЛЬТРАЦИЯ: пропускаем мусорные строки
                if title and not re.match(r"^[/\s\-\.,_]+$", title):
                    tracks.append({"duration": duration, "title": title})
                    i = j; break
                j += 1
        i += 1
    
    chapters = []
    current_start = 0
    for t in tracks:
        dur_sec = parse_time_to_seconds(t["duration"])
        chapters.append({"title": t["title"], "start": current_start, "end": current_start + dur_sec})
        current_start += dur_sec
    return chapters

async def get_book_info(book_url):
    log_debug(f"Combined info scraping: {book_url}")
    res = {"m3u8": None, "title": "audiobook", "chapters": []}
    
    # 0. МАРШРУТИЗАТОР: Обработка специфичных сайтов (например, knigavuhe.org)
    if "knigavuhe.org" in book_url:
        log_debug("Detected knigavuhe.org, using dedicated fast parser...")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with httpx.AsyncClient(http2=True) as client:
                resp = await client.get(book_url, headers=headers, timeout=20, follow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    h1 = soup.find("h1")
                    if h1: res["title"] = sanitize_filename(h1.get_text().strip())
                    
                    # Ищем JSON со списком треков
                    match = re.search(r'\[\{.*?"title".*?"url".*?\}\]', resp.text)
                    if match:
                        data = json.loads(match.group(0))
                        direct_urls = []
                        current_start = 0
                        for item in data:
                            title = item.get("title", "")
                            url = item.get("url", "")
                            dur = item.get("duration", 0)
                            if url:
                                direct_urls.append(url)
                                res["chapters"].append({
                                    "title": title,
                                    "start": current_start,
                                    "end": current_start + dur
                                })
                                current_start += dur
                        log_debug(f"Knigavuhe: Found {len(direct_urls)} tracks")
                        # Передаем список URL как строку, разделенную запятыми, с префиксом
                        res["m3u8"] = "DIRECT_URLS:" + ",".join(direct_urls)
                        return res["m3u8"], res["title"], res["chapters"]
        except Exception as e:
            log_debug(f"Knigavuhe parse error: {e}")
            return None, "audiobook", []

    # Text-based parsing (Fast) для остальных сайтов
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://akniga.org/"
        }
        async with httpx.AsyncClient(http2=True) as client:
            resp = await client.get(book_url, headers=headers, timeout=20, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                h1 = soup.find("h1")
                if h1: res["title"] = h1.get_text().strip()
                res["chapters"] = extract_chapters_from_html(resp.text)
    except Exception as e: log_debug(f"BS4 parse error: {e}")

    # Browser-based parsing (for m3u8)
    try:
        if browser_instance:
            log_debug("Using persistent Playwright browser instance")
            context = await browser_instance.new_context()
            page = await context.new_page()
            
            # Блокируем только картинки и медиа для скорости (оставляем CSS, так как он может быть нужен плееру)
            await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,ico}", lambda route: route.abort())
            page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)
            
            await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)
            
            for _ in range(15):
                if res["m3u8"]: break
                if _ == 5:
                    try:
                        # Агрессивный клик через JS работает надежнее
                        await page.evaluate("document.querySelector('.button__player--play, .js-player-play')?.click()")
                        log_debug("Play clicked via JS")
                    except: pass
                await asyncio.sleep(1)

            if not res["chapters"]:
                log_debug("BS4 chapters empty, parsing DOM elements...")
                res["chapters"] = await page.evaluate("""() => {
                    let items = [];
                    
                    // 1. Try standard akniga layout (.ls-item)
                    let standardItems = document.querySelectorAll('.ls-item');
                    if (standardItems.length > 0) {
                        standardItems.forEach(el => {
                            let titleEl = el.querySelector('.ls-title');
                            if (titleEl) {
                                items.push({
                                    title: titleEl.innerText.trim(),
                                    start: parseFloat(el.getAttribute('data-time') || 0),
                                    end: 0
                                });
                            }
                        });
                    }
                    
                    // 2. Try old/alternative akniga layout (.chapter__default)
                    if (items.length === 0) {
                        let oldItems = document.querySelectorAll('.chapter__default');
                        if (oldItems.length > 0) {
                            oldItems.forEach(el => {
                                let titleEl = el.querySelector('.chapter__default--title');
                                let pos = el.getAttribute('data-pos');
                                if (titleEl && pos !== null) {
                                    items.push({
                                        title: titleEl.innerText.trim(),
                                        start: parseFloat(pos),
                                        end: 0
                                    });
                                }
                            });
                        }
                    }

                    // 3. Post-process to set 'end' times
                    for (let i = 0; i < items.length; i++) {
                        if (i < items.length - 1) {
                            items[i].end = items[i+1].start;
                        }
                    }

                    // 4. Try Global JS Variables (highest priority if found)
                    let jsData = window.items || window.playlist || window.free_playlist;
                    if (jsData && Array.isArray(jsData) && jsData.length > 0) {
                        return jsData.map(i => ({
                            title: i.title || i.name || "Chapter", 
                            start: parseFloat(i.time_from_start || i.start || 0), 
                            end: parseFloat(i.time_finish || i.end || 0)
                        }));
                    }
                    
                    return items;
                }""")
                log_debug(f"DOM parsing found {len(res['chapters'])} chapters")
            
            if not res["chapters"] and res["title"] != "audiobook":
                res["chapters"] = [{"title": res["title"], "start": 0, "end": 0}]

            await context.close()
        else:
            log_debug("Persistent browser not found, launching temporary instance...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Блокируем только картинки и медиа для скорости (оставляем CSS, так как он может быть нужен плееру)
                await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,ico}", lambda route: route.abort())
                page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)
                
                await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)
                
                for _ in range(15):
                    if res["m3u8"]: break
                    if _ == 5:
                        try:
                            # Агрессивный клик через JS работает надежнее
                            await page.evaluate("document.querySelector('.button__player--play, .js-player-play')?.click()")
                            log_debug("Play clicked via JS")
                        except: pass
                    await asyncio.sleep(1)

                if not res["chapters"]:
                    log_debug("BS4 chapters empty, parsing DOM elements...")
                    res["chapters"] = await page.evaluate("""() => {
                        let items = [];
                        
                        // 1. Try standard akniga layout (.ls-item)
                        let standardItems = document.querySelectorAll('.ls-item');
                        if (standardItems.length > 0) {
                            standardItems.forEach(el => {
                                let titleEl = el.querySelector('.ls-title');
                                if (titleEl) {
                                    items.push({
                                        title: titleEl.innerText.trim(),
                                        start: parseFloat(el.getAttribute('data-time') || 0),
                                        end: 0
                                    });
                                }
                            });
                        }
                        
                        // 2. Try old/alternative akniga layout (.chapter__default)
                        if (items.length === 0) {
                            let oldItems = document.querySelectorAll('.chapter__default');
                            if (oldItems.length > 0) {
                                oldItems.forEach(el => {
                                    let titleEl = el.querySelector('.chapter__default--title');
                                    let pos = el.getAttribute('data-pos');
                                    if (titleEl && pos !== null) {
                                        items.push({
                                            title: titleEl.innerText.trim(),
                                            start: parseFloat(pos),
                                            end: 0
                                        });
                                    }
                                });
                            }
                        }

                        // 3. Post-process to set 'end' times
                        for (let i = 0; i < items.length; i++) {
                            if (i < items.length - 1) {
                                items[i].end = items[i+1].start;
                            }
                        }

                        // 4. Try Global JS Variables (highest priority if found)
                        let jsData = window.items || window.playlist || window.free_playlist;
                        if (jsData && Array.isArray(jsData) && jsData.length > 0) {
                            return jsData.map(i => ({
                                title: i.title || i.name || "Chapter", 
                                start: parseFloat(i.time_from_start || i.start || 0), 
                                end: parseFloat(i.time_finish || i.end || 0)
                            }));
                        }
                        
                        return items;
                    }""")
                    log_debug(f"DOM parsing found {len(res['chapters'])} chapters")
                
                if not res["chapters"] and res["title"] != "audiobook":
                    res["chapters"] = [{"title": res["title"], "start": 0, "end": 0}]

                await browser.close()
    except Exception as e: log_debug(f"Playwright error: {e}")

    return res["m3u8"], res["title"], res["chapters"]
