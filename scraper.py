import re
import asyncio
import json
import logging
import base64
import binascii
import html
import os
import time
import copy
import threading
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from media_helpers import sanitize_filename
import config

logger = logging.getLogger(__name__)

def log_debug(message):
    logger.info(message)

DEFAULT_BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Persistent Playwright browser instance
playwright_instance = None
browser_instance = None
browser_start_error = ""
PREVIEW_CACHE_TTL_SECONDS = int(os.getenv("SONICBOOK_PREVIEW_CACHE_TTL_SECONDS", "900"))
PREVIEW_CACHE_FILE = os.path.join(config.BASE_DIR, ".sonicbook-state", "preview_cache.json")
_preview_cache = {}
_preview_cache_lock = threading.RLock()


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
        except (PlaywrightError, OSError, RuntimeError) as e:
            browser_start_error = describe_playwright_issue(e)
            logger.exception("Persistent Playwright browser initialization failed: %s", browser_start_error)
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                except (PlaywrightError, OSError, RuntimeError):
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


def _normalize_cache_url(url: str) -> str:
    return str(url or "").strip()


def _normalize_chapter_payload(chapter) -> dict | None:
    if not isinstance(chapter, dict):
        return None
    title = str(chapter.get("title") or "").strip()
    if not title:
        title = "Chapter"
    try:
        start = float(chapter.get("start") or 0)
    except (TypeError, ValueError):
        start = 0.0
    try:
        end = float(chapter.get("end") or 0)
    except (TypeError, ValueError):
        end = 0.0
    return {
        "title": title,
        "start": start,
        "end": end,
    }


def _normalize_preview_cache_entry(entry) -> dict | None:
    if not isinstance(entry, dict):
        return None

    try:
        created_at = float(entry.get("created_at") or 0)
    except (TypeError, ValueError):
        return None

    result = entry.get("result")
    if not isinstance(result, dict):
        return None

    m3u8 = str(result.get("m3u8") or "").strip()
    if not m3u8:
        return None

    title = str(result.get("title") or "audiobook").strip() or "audiobook"
    cover_value = result.get("cover")
    cover = str(cover_value).strip() if cover_value else None

    chapters = result.get("chapters")
    normalized_chapters = []
    if isinstance(chapters, list):
        for chapter in chapters:
            normalized = _normalize_chapter_payload(chapter)
            if normalized is not None:
                normalized_chapters.append(normalized)

    return {
        "created_at": created_at,
        "result": {
            "m3u8": m3u8,
            "title": title,
            "chapters": normalized_chapters,
            "cover": cover,
        },
    }


def _prune_preview_cache_entries(entries: dict | None) -> dict:
    now_ts = time.time()
    normalized = {}
    source = entries if isinstance(entries, dict) else {}
    for raw_url, raw_entry in source.items():
        url = _normalize_cache_url(raw_url)
        if not url:
            continue
        entry = _normalize_preview_cache_entry(raw_entry)
        if entry is None:
            continue
        if now_ts - float(entry["created_at"]) > PREVIEW_CACHE_TTL_SECONDS:
            continue
        normalized[url] = entry
    return normalized


def _write_preview_cache_file(entries: dict):
    os.makedirs(os.path.dirname(PREVIEW_CACHE_FILE), exist_ok=True)
    temp_path = PREVIEW_CACHE_FILE + ".tmp"
    payload = {
        "entries": entries,
        "updated_at": time.time(),
    }
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, PREVIEW_CACHE_FILE)


def _save_preview_cache_to_disk():
    with _preview_cache_lock:
        snapshot = _prune_preview_cache_entries(_preview_cache)
        _preview_cache.clear()
        _preview_cache.update(snapshot)

    with config.locked_json_file(PREVIEW_CACHE_FILE):
        try:
            if not snapshot:
                if os.path.exists(PREVIEW_CACHE_FILE):
                    os.remove(PREVIEW_CACHE_FILE)
                return
            _write_preview_cache_file(snapshot)
        except (OSError, TypeError, ValueError):
            logger.warning("Failed to persist preview cache", exc_info=True)


def _load_preview_cache_from_disk():
    with config.locked_json_file(PREVIEW_CACHE_FILE):
        if not os.path.exists(PREVIEW_CACHE_FILE):
            entries = {}
        else:
            try:
                with open(PREVIEW_CACHE_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (OSError, json.JSONDecodeError):
                entries = {}
            else:
                if isinstance(payload, dict):
                    entries = payload.get("entries", {})
                else:
                    entries = {}
        pruned = _prune_preview_cache_entries(entries)
        if pruned != entries:
            try:
                if pruned:
                    _write_preview_cache_file(pruned)
                elif os.path.exists(PREVIEW_CACHE_FILE):
                    os.remove(PREVIEW_CACHE_FILE)
            except (OSError, TypeError, ValueError):
                logger.warning("Failed to rewrite preview cache", exc_info=True)

    with _preview_cache_lock:
        _preview_cache.clear()
        _preview_cache.update(pruned)


def _get_cached_book_info(book_url: str):
    url = _normalize_cache_url(book_url)
    if not url:
        return None

    with _preview_cache_lock:
        entry = _preview_cache.get(url)
        if entry is None:
            return None
        if time.time() - float(entry.get("created_at") or 0) > PREVIEW_CACHE_TTL_SECONDS:
            del _preview_cache[url]
            should_persist = True
        else:
            should_persist = False
            result = copy.deepcopy(entry.get("result", {}))

    if should_persist:
        _save_preview_cache_to_disk()
        return None

    m3u8 = result.get("m3u8")
    title = result.get("title", "audiobook")
    chapters = result.get("chapters", [])
    cover = result.get("cover")
    return m3u8, title, chapters, cover


def _cache_book_info(book_url: str, m3u8: str, title: str, chapters: list, cover):
    url = _normalize_cache_url(book_url)
    if not url or not m3u8:
        return

    normalized_chapters = []
    for chapter in (chapters or []):
        normalized = _normalize_chapter_payload(chapter)
        if normalized is not None:
            normalized_chapters.append(normalized)

    cover_value = str(cover).strip() if cover else None
    entry = {
        "created_at": time.time(),
        "result": {
            "m3u8": str(m3u8),
            "title": str(title or "audiobook"),
            "chapters": normalized_chapters,
            "cover": cover_value,
        },
    }
    with _preview_cache_lock:
        _preview_cache[url] = entry
    _save_preview_cache_to_disk()


_load_preview_cache_from_disk()

def parse_time_to_seconds(time_str):
    try:
        parts = time_str.split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (AttributeError, TypeError, ValueError):
        pass
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
        except (binascii.Error, UnicodeDecodeError, ValueError):
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
    except (httpx.HTTPError, json.JSONDecodeError, OSError, TypeError, ValueError, re.error) as e:
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
    except (httpx.HTTPError, OSError, TypeError, ValueError) as e:
        log_debug(f"BS4 parse error: {e}")

async def _extract_playwright_data(page, res, book_url):
    """Core logic to interact with the page and extract m3u8 and chapters."""
    await page.route("**/*.{png,jpg,jpeg,svg,woff,woff2,ico}", lambda route: route.abort())
    page.on("request", lambda r: res.update({"m3u8": r.url}) if ".m3u8" in r.url else None)

    await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)

    # Dedicated extraction for akniga.org via page JS context
    if "akniga.org" in book_url or await page.evaluate("() => typeof plh !== 'undefined' && typeof plh.getHres === 'function'"):
        akniga_data = await page.evaluate("""async () => {
            try {
                let bid = (typeof page_bid !== 'undefined' && page_bid) || parseInt(document.querySelector('article')?.getAttribute('data-bid'));
                if (!bid) return null;
                let hasPlh = typeof plh !== 'undefined' && typeof plh.getHres === 'function';
                if (!hasPlh) return null;

                let hlsRes = (typeof bookData !== 'undefined' && bookData && bookData[bid] && bookData[bid].hres) ? bookData[bid] : null;
                if (!hlsRes) {
                    let token = await new Promise(r => {
                        if (typeof ls !== 'undefined' && ls.ajax) {
                            ls.ajax.load(aRouter['ajax'] + 'player/token', {bid: bid}, function(res) {
                                r(res && res.token);
                            }, {showProgress: false, onError: () => r(null)});
                        } else {
                            r(null);
                        }
                    });
                    if (token) {
                        hlsRes = await new Promise(r => {
                            ls.ajax.load(aRouter['ajax'] + 'b/' + bid, {bid: bid, token: token, hls: 'true'}, function(res) {
                                r(res);
                            }, {showProgress: false, onError: () => r(null)});
                        });
                    }
                }

                if (hlsRes && hlsRes.hres) {
                    let hlsUrl = plh.getHres(hlsRes.hres);
                    let items = hlsRes.items ? (typeof hlsRes.items === 'string' ? JSON.parse(hlsRes.items) : hlsRes.items) : [];
                    let chapters = items.map(i => ({
                        title: i.title || i.name || "Chapter",
                        start: parseFloat(i.time_from_start || i.start || 0),
                        end: parseFloat(i.time_finish || i.end || 0)
                    }));
                    return {
                        m3u8: hlsUrl,
                        title: hlsRes.title || '',
                        chapters: chapters
                    };
                }
            } catch (e) {
                console.warn('akniga player extract error:', e);
            }
            return null;
        }""")
        if akniga_data and akniga_data.get("m3u8"):
            res["m3u8"] = akniga_data["m3u8"]
            if akniga_data.get("chapters"):
                res["chapters"] = akniga_data["chapters"]
            if akniga_data.get("title") and res["title"] == "audiobook":
                res["title"] = sanitize_filename(akniga_data["title"])
            log_debug(f"Akniga fast extraction succeeded: m3u8 found, {len(res['chapters'])} chapters")

    for _ in range(15):
        if res["m3u8"]: break
        if _ == 5:
            try:
                await page.evaluate("document.querySelector('.button__player--play, .js-player-play')?.click()")
                log_debug("Play clicked via JS")
            except (PlaywrightError, RuntimeError):
                pass
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
                context = await browser_instance.new_context(user_agent=DEFAULT_BROWSER_USER_AGENT, locale="ru-RU")
                page = await context.new_page()
            except (PlaywrightError, OSError, RuntimeError) as e:
                log_debug(f"Persistent browser context failed, attempting respawn: {e}")
                await close_browser()
                await init_browser()
                if not browser_instance:
                    raise RuntimeError("Failed to respawn browser instance")
                context = await browser_instance.new_context(user_agent=DEFAULT_BROWSER_USER_AGENT, locale="ru-RU")
                page = await context.new_page()

            await _extract_playwright_data(page, res, book_url)

            await context.close()
        else:
            if browser_start_error:
                log_debug(f"Persistent Playwright unavailable: {browser_start_error}")
            log_debug("Persistent browser not found, launching temporary instance...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=DEFAULT_BROWSER_USER_AGENT, locale="ru-RU")
                page = await context.new_page()
                
                await _extract_playwright_data(page, res, book_url)

                await context.close()
                await browser.close()
    except (PlaywrightError, OSError, RuntimeError) as e:
        playwright_failure = describe_playwright_issue(e)
        logger.exception("Playwright scraping failed: %s", playwright_failure)

    return playwright_failure

async def get_book_info(book_url):
    book_url = _normalize_cache_url(book_url)
    cached = _get_cached_book_info(book_url)
    if cached is not None:
        log_debug(f"Preview cache hit: {book_url}")
        return cached

    log_debug(f"Combined info scraping: {book_url}")
    res = {"m3u8": None, "title": "audiobook", "chapters": [], "cover": None}
    playwright_failure = ""

    if "knigavuhe.org" in book_url:
        m3u8, title, chapters, cover = await _parse_knigavuhe(book_url)
        if m3u8:
            _cache_book_info(book_url, m3u8, title, chapters, cover)
        return m3u8, title, chapters, cover

    if "audioboo.org" in book_url:
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
                        _cache_book_info(book_url, res["m3u8"], res["title"], [], res["cover"])
                        return res["m3u8"], res["title"], [], res["cover"]
        except (httpx.HTTPError, OSError, TypeError, ValueError) as e:
            log_debug(f"Audioboo parse error: {e}")
            return None, "audiobook", [], None

    await _parse_text_based(book_url, res)
    
    playwright_failure = await _parse_browser_based(book_url, res)

    if not res["m3u8"] and playwright_failure:
        raise RuntimeError(playwright_failure)

    if res["m3u8"]:
        _cache_book_info(book_url, res["m3u8"], res["title"], res["chapters"], res["cover"])

    return res["m3u8"], res["title"], res["chapters"], res["cover"]
