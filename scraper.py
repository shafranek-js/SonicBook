import re
import asyncio
import json
import logging
import base64
import html
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import config
from processor import sanitize_filename

logger = logging.getLogger(__name__)

def log_debug(message):
    logger.info(message)

# Persistent Playwright browser instance
playwright_instance = None
browser_instance = None
browser_start_error = ""


def describe_playwright_issue(exc: Exception) -> str:
    message = str(exc or "").strip()
    lowered = message.lower()
    winerror = getattr(exc, "winerror", None)

    if isinstance(exc, PermissionError) or winerror == 5 or "access is denied" in lowered:
        return (
            "Playwright Chromium launch was blocked by Windows permissions or antivirus. "
            "Try running SonicBook once as administrator, add the Playwright browser folder to antivirus exclusions, "
            "and verify Chromium is installed with 'playwright install chromium'."
        )
    if "executable doesn't exist" in lowered or "browserType.launch" in lowered and "executable" in lowered:
        return "Playwright Chromium is not installed. Run 'playwright install chromium' and try again."
    if "target page, context or browser has been closed" in lowered:
        return "Playwright browser closed unexpectedly while scraping the page."
    if isinstance(exc, PlaywrightTimeoutError) or "timeout" in lowered:
        return "Playwright timed out while opening the page."
    return f"Playwright browser error: {message or exc.__class__.__name__}"

async def init_browser():
    global playwright_instance, browser_instance, browser_start_error
    if not playwright_instance:
        log_debug("Initializing persistent Playwright browser...")
        try:
            playwright_instance = await async_playwright().start()
            browser_instance = await playwright_instance.chromium.launch(headless=True)
            browser_start_error = ""
        except Exception as e:
            browser_start_error = describe_playwright_issue(e)
            logger.exception("Persistent Playwright browser initialization failed: %s", browser_start_error)
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                except Exception:
                    pass
            playwright_instance = None
            browser_instance = None

async def close_browser():
    global playwright_instance, browser_instance, browser_start_error
    if browser_instance:
        await browser_instance.close()
    if playwright_instance:
        await playwright_instance.stop()
    playwright_instance = None
    browser_instance = None
    browser_start_error = ""

def parse_time_to_seconds(time_str):
    try:
        parts = time_str.split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except: pass
    return 0

def extract_cover_url(soup, page_url):
    candidate_selectors = [
        ("meta", {"property": "og:image"}, "content"),
        ("meta", {"name": "twitter:image"}, "content"),
        ("meta", {"name": "twitter:image:src"}, "content"),
        ("img", {"itemprop": "image"}, "src"),
        ("img", {"class": "book__cover"}, "src"),
        ("img", {"class": "book_cover"}, "src"),
    ]

    for tag_name, attrs, attr_name in candidate_selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get(attr_name):
            return urljoin(page_url, tag.get(attr_name))

    fallback = soup.find("img", src=re.compile(r"/uploads/media/topic/"))
    if fallback and fallback.get("src"):
        return urljoin(page_url, fallback.get("src"))

    return None

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

def extract_audioboo_zip_url(html_content: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html_content, "html.parser")

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if "engine/go.php?url=" not in href:
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        encoded = (parse_qs(parsed.query).get("url") or [""])[0].strip()
        if not encoded:
            continue

        try:
            raw = unquote(encoded)
            padded = raw + ("=" * (-len(raw) % 4))
            decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
            normalized = html.unescape(decoded).strip()
            if normalized.startswith("http://") or normalized.startswith("https://"):
                return normalized
        except Exception:
            continue

    return None

async def _parse_knigavuhe(book_url):
    log_debug("Detected knigavuhe.org, using dedicated fast parser...")
    res = {"m3u8": None, "title": "audiobook", "chapters": [], "cover": None}
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(http2=True) as client:
            resp = await client.get(book_url, headers=headers, timeout=20, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                h1 = soup.find("h1")
                if h1: res["title"] = sanitize_filename(h1.get_text().strip())

                res["cover"] = extract_cover_url(soup, book_url)

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
                    res["m3u8"] = "DIRECT_URLS:" + ",".join(direct_urls)
                    return res["m3u8"], res["title"], res["chapters"], res["cover"]
    except Exception as e:
        log_debug(f"Knigavuhe parse error: {e}")
    return None, "audiobook", [], None

async def _parse_text_based(book_url, res):
    """Text-based parsing (Fast) для остальных сайтов."""
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
                
                res["cover"] = extract_cover_url(soup, book_url)
                    
                res["chapters"] = extract_chapters_from_html(resp.text)
    except Exception as e:
        log_debug(f"BS4 parse error: {e}")

async def _extract_playwright_data(page, res, book_url):
    """Core logic to interact with the page and extract m3u8 and chapters."""
    await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,ico}", lambda route: route.abort())
    page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)

    await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)

    for _ in range(15):
        if res["m3u8"]: break
        if _ == 5:
            try:
                await page.evaluate("document.querySelector('.button__player--play, .js-player-play')?.click()")
                log_debug("Play clicked via JS")
            except: pass
        await asyncio.sleep(1)

    if not res["chapters"]:
        log_debug("BS4 chapters empty, parsing DOM elements...")
        res["chapters"] = await page.evaluate("""() => {
            let items = [];

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

            for (let i = 0; i < items.length; i++) {
                if (i < items.length - 1) {
                    items[i].end = items[i+1].start;
                }
            }

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

async def _parse_browser_based(book_url, res):
    """Browser-based parsing (for m3u8) using either persistent or temp Playwright instance."""
    playwright_failure = ""
    try:
        if browser_instance:
            log_debug("Using persistent Playwright browser instance")
            try:
                context = await browser_instance.new_context()
                page = await context.new_page()
            except Exception as e:
                log_debug(f"Persistent browser context failed, attempting respawn: {e}")
                await close_browser()
                await init_browser()
                if not browser_instance:
                    raise RuntimeError("Failed to respawn browser instance")
                context = await browser_instance.new_context()
                page = await context.new_page()

            await _extract_playwright_data(page, res, book_url)

            await context.close()
        else:
            if browser_start_error:
                log_debug(f"Persistent Playwright unavailable: {browser_start_error}")
            log_debug("Persistent browser not found, launching temporary instance...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await _extract_playwright_data(page, res, book_url)

                await browser.close()
    except Exception as e:
        playwright_failure = describe_playwright_issue(e)
        logger.exception("Playwright scraping failed: %s", playwright_failure)

    return playwright_failure

async def _parse_audioboo(book_url, res):
    log_debug("Detected audioboo.org, using ZIP parser...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
            resp = await client.get(book_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                h1 = soup.find("h1")
                if h1:
                    res["title"] = h1.get_text(" ", strip=True)

                res["cover"] = extract_cover_url(soup, book_url)
                zip_url = extract_audioboo_zip_url(resp.text, str(resp.url))
                if zip_url:
                    log_debug(f"Audioboo: Found direct ZIP URL {zip_url}")
                    res["m3u8"] = f"DIRECT_ZIP:{zip_url}"
                    return res["m3u8"], res["title"], res["chapters"], res["cover"]
    except Exception as e:
        log_debug(f"Audioboo parse error: {e}")
        return None, "audiobook", [], None

    return None

async def get_book_info(book_url):
    log_debug(f"Combined info scraping: {book_url}")
    res = {"m3u8": None, "title": "audiobook", "chapters": [], "cover": None}
    playwright_failure = ""

    if "knigavuhe.org" in book_url:
        return await _parse_knigavuhe(book_url)

    if "audioboo.org" in book_url:
        audioboo_res = await _parse_audioboo(book_url, res)
        if audioboo_res is not None:
            return audioboo_res

    await _parse_text_based(book_url, res)
    
    playwright_failure = await _parse_browser_based(book_url, res)

    if not res["m3u8"] and playwright_failure:
        raise RuntimeError(playwright_failure)

    return res["m3u8"], res["title"], res["chapters"], res["cover"]
