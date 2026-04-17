import asyncio
import json
import os
import re
from io import BytesIO
from urllib.parse import quote

import httpx
from PIL import Image
import aiofiles

import config
import scraper
from processor import resolve_cover_extension

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SonicBook cover-backfill/1.0"
AUDIO_EXTENSIONS = (".m4b", ".mp3", ".mp4", ".m4a", ".zip")
MIN_COVER_EDGE = 120
ALIASES_FILE = os.path.join(config.BASE_DIR, "cover_aliases.json")
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "").strip()


def iter_audio_files():
    for entry in sorted(os.listdir(config.DOWNLOADS_DIR)):
        if entry.endswith(AUDIO_EXTENSIONS):
            yield entry


def metadata_path_for(file_name: str) -> str:
    base_name = os.path.splitext(file_name)[0]
    return os.path.join(config.DOWNLOADS_DIR, f"{base_name}.json")


def load_metadata(file_name: str) -> dict:
    path = metadata_path_for(file_name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metadata(file_name: str, metadata: dict):
    path = metadata_path_for(file_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def detect_existing_cover(base_name: str) -> str | None:
    for ext in (".jpg", ".png", ".webp"):
        candidate = os.path.join(config.DOWNLOADS_DIR, f"{base_name}{ext}")
        if os.path.exists(candidate):
            return os.path.basename(candidate)
    return None


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def title_score(candidate_title: str, desired_titles: list[str]) -> int:
    candidate = normalize_text(candidate_title)
    if not candidate:
        return 0

    score = 0
    for desired in desired_titles:
        normalized = normalize_text(desired)
        if not normalized:
            continue
        if candidate == normalized:
            score += 100
        elif (len(normalized) >= 8 or len(normalized.split()) >= 2) and normalized in candidate:
            score += 60
        elif (len(candidate) >= 8 or len(candidate.split()) >= 2) and candidate in normalized:
            score += 40
    return score


def author_score(candidate_authors, desired_author: str) -> int:
    desired = normalize_text(desired_author)
    if not desired:
        return 0

    if isinstance(candidate_authors, str):
        candidate_authors = [candidate_authors]

    score = 0
    for author in candidate_authors or []:
        normalized = normalize_text(author)
        if not normalized:
            continue
        if normalized == desired:
            score += 100
        elif desired in normalized or normalized in desired:
            score += 60
    return score


def best_author_score(candidate_authors, authors: list[str]) -> int:
    return max((author_score(candidate_authors, author) for author in authors), default=0)


def is_viable_match(title_match: int, author_match: int) -> bool:
    if title_match >= 100:
        return True
    if title_match >= 60 and author_match >= 60:
        return True
    return False


async def load_aliases() -> dict:
    if not await asyncio.to_thread(os.path.exists, ALIASES_FILE):
        return {}
    async with aiofiles.open(ALIASES_FILE, "r", encoding="utf-8") as f:
        content = await f.read()
        return await asyncio.to_thread(json.loads, content)


def alias_entry_for(file_name: str, metadata: dict, aliases: dict) -> dict:
    base_name = os.path.splitext(file_name)[0]
    title = metadata.get("title") or base_name
    return aliases.get(base_name) or aliases.get(title) or {}


def parse_author_title(file_name: str, metadata: dict, aliases: dict) -> tuple[list[str], list[str]]:
    base_name = os.path.splitext(file_name)[0]
    title = metadata.get("title") or base_name
    entry = alias_entry_for(file_name, metadata, aliases)

    titles = []
    authors = []

    alias_titles = entry.get("search_titles") or []
    alias_authors = entry.get("search_authors") or []

    def add_unique(target: list[str], value: str | None):
        if value and value not in target:
            target.append(value)

    add_unique(titles, title)
    for alias_title in alias_titles:
        add_unique(titles, alias_title)

    if " - " in title:
        author_part, title_part = title.split(" - ", 1)
        add_unique(authors, author_part)
        add_unique(titles, title_part)

    normalized = re.sub(r"\([^)]*\)", "", title)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip(" -")
    add_unique(titles, normalized)
    if " - " in normalized:
        author_part, title_part = normalized.split(" - ", 1)
        add_unique(authors, author_part)
        add_unique(titles, title_part)

    for alias_author in alias_authors:
        add_unique(authors, alias_author)

    return titles, authors


def is_latin_text(value: str) -> bool:
    return any("a" <= ch.lower() <= "z" for ch in value)


def prioritized_titles(titles: list[str]) -> list[str]:
    split_titles = []
    full_titles = []
    for title in titles:
        if not title:
            continue
        if " - " in title:
            full_titles.append(title)
        else:
            split_titles.append(title)
    return split_titles + full_titles


def prioritized_authors(authors: list[str]) -> list[str]:
    latin_authors = []
    other_authors = []
    for author in authors:
        if not author:
            continue
        if is_latin_text(author):
            latin_authors.append(author)
        else:
            other_authors.append(author)
    return latin_authors + other_authors


def iter_search_pairs(titles: list[str], authors: list[str], limit_titles: int = 6, limit_authors: int = 3):
    seen = set()
    ordered_titles = prioritized_titles(titles)[:limit_titles]
    ordered_authors = prioritized_authors(authors)[:limit_authors]

    for title in ordered_titles:
        for author in ordered_authors:
            pair = (title, author)
            if pair in seen:
                continue
            seen.add(pair)
            yield pair

        pair = (title, None)
        if pair in seen:
            continue
        seen.add(pair)
        yield pair


def candidate_rank(candidate: dict) -> tuple[int, int, int]:
    source_bonus = 0
    if candidate["source"] == "google_books":
        source_bonus = {
            "extraLarge": 30,
            "large": 20,
            "medium": 10,
        }.get(candidate.get("size_name"), 0)
    elif candidate["source"] == "open_library":
        source_bonus = {"L": 10, "M": 5}.get(candidate.get("size_name"), 0)
    elif candidate["source"] == "metadata":
        source_bonus = 20
    elif candidate["source"] == "source_url":
        source_bonus = 25
    elif candidate["source"] == "akniga":
        source_bonus = 15

    return (candidate["score"], candidate["pixels"], source_bonus)


async def fetch_image_candidate(client: httpx.AsyncClient, candidate: dict) -> dict | None:
    try:
        response = await client.get(candidate["url"], follow_redirects=True)
        if response.status_code != 200:
            return None

        image_bytes = response.content
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
            fmt = (img.format or "").lower()

        if width < MIN_COVER_EDGE or height < MIN_COVER_EDGE:
            return None

        result = dict(candidate)
        result["image_bytes"] = image_bytes
        result["width"] = width
        result["height"] = height
        result["pixels"] = width * height
        result["content_type"] = response.headers.get("content-type", "")
        result["format"] = fmt
        return result
    except Exception:
        return None


async def fetch_cover_from_source_url(source_url: str) -> str | None:
    _, _, _, cover_url = await scraper.get_book_info(source_url)
    return cover_url


async def search_akniga_candidates(titles: list[str], authors: list[str]) -> list[dict]:
    if not scraper.browser_instance:
        await scraper.init_browser()

    candidates = []
    seen = set()
    query_terms = titles[:]
    for author in authors:
        for title in titles:
            query_terms.append(f"{author} {title}")

    for query in query_terms[:6]:
        page = await scraper.browser_instance.new_page()
        try:
            search_url = f"https://akniga.org/search/?q={quote(query)}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            links = await page.eval_on_selector_all(
                "a.content__main__books--item--title, .content__main__books--item a, .ls-item a",
                """(nodes) => nodes.slice(0, 5).map(node => ({
                    href: node.getAttribute('href'),
                    text: (node.textContent || '').trim()
                }))""",
            )
            for item in links:
                href = item.get("href")
                if not href:
                    continue
                if not href.startswith("http"):
                    href = "https://akniga.org" + href
                if href in seen:
                    continue
                seen.add(href)
                cover_url = await fetch_cover_from_source_url(href)
                if cover_url:
                    title_match = title_score(item.get("text", ""), titles)
                    author_match = best_author_score(item.get("text", ""), authors)
                    if not is_viable_match(title_match, author_match):
                        continue
                    score = title_match + author_match
                    candidates.append({
                        "source": "akniga",
                        "title": item.get("text", ""),
                        "authors": [],
                        "score": score,
                        "size_name": "page",
                        "url": cover_url,
                    })
        except Exception:
            continue
        finally:
            await page.close()

    return candidates


async def search_open_library_candidates(titles: list[str], authors: list[str]) -> list[dict]:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20) as client:
        candidates = []
        seen = set()
        for title, author in iter_search_pairs(titles, authors):
            params = {"title": title, "limit": 5, "fields": "title,author_name,cover_i,cover_edition_key,edition_key"}
            if author:
                params["author"] = author
            response = await client.get("https://openlibrary.org/search.json", params=params)
            if response.status_code != 200:
                continue
            payload = response.json()
            for doc in payload.get("docs") or []:
                doc_title = doc.get("title", "")
                doc_authors = doc.get("author_name", [])
                title_match = title_score(doc_title, titles)
                author_match = best_author_score(doc_authors, authors)
                if not is_viable_match(title_match, author_match):
                    continue
                score = title_match + author_match

                cover_id = doc.get("cover_i")
                cover_olid = doc.get("cover_edition_key")
                edition_keys = doc.get("edition_key") or []
                if not cover_olid and edition_keys:
                    cover_olid = edition_keys[0]

                for size_name in ("L", "M", "S"):
                    url = None
                    if cover_olid:
                        url = f"https://covers.openlibrary.org/b/olid/{cover_olid}-{size_name}.jpg"
                    elif cover_id:
                        url = f"https://covers.openlibrary.org/b/id/{cover_id}-{size_name}.jpg"
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    candidates.append({
                        "source": "open_library",
                        "title": doc_title,
                        "authors": doc_authors,
                        "score": score,
                        "size_name": size_name,
                        "url": url,
                    })
        return candidates


async def search_google_books_candidates(titles: list[str], authors: list[str]) -> list[dict]:
    candidates = []
    seen = set()
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20) as client:
        for title, author in iter_search_pairs(titles, authors):
            query = f'intitle:"{title}"'
            if author:
                query += f' inauthor:"{author}"'
            params = {
                "q": query,
                "printType": "books",
                "projection": "full",
                "maxResults": 5,
            }
            if GOOGLE_BOOKS_API_KEY:
                params["key"] = GOOGLE_BOOKS_API_KEY

            response = await client.get("https://www.googleapis.com/books/v1/volumes", params=params)
            if response.status_code == 429:
                break
            if response.status_code != 200:
                continue

            payload = response.json()
            for item in payload.get("items") or []:
                info = item.get("volumeInfo") or {}
                book_title = info.get("title", "")
                book_authors = info.get("authors", [])
                image_links = info.get("imageLinks") or {}
                title_match = title_score(book_title, titles)
                author_match = best_author_score(book_authors, authors)
                if not is_viable_match(title_match, author_match):
                    continue
                score = title_match + author_match

                for size_name in ("extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail"):
                    url = image_links.get(size_name)
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    candidates.append({
                        "source": "google_books",
                        "title": book_title,
                        "authors": book_authors,
                        "score": score,
                        "size_name": size_name,
                        "url": url,
                    })
        return candidates


async def find_cover_candidates(file_name: str, metadata: dict, aliases: dict) -> list[dict]:
    titles, authors = parse_author_title(file_name, metadata, aliases)
    alias_entry = alias_entry_for(file_name, metadata, aliases)
    candidates = []
    seen = set()

    def add_candidate(candidate: dict | None):
        if not candidate:
            return
        key = candidate["url"]
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)

    if metadata.get("cover_url"):
        add_candidate({
            "source": "metadata",
            "title": metadata.get("title", ""),
            "authors": authors,
            "score": 300,
            "size_name": "existing",
            "url": metadata["cover_url"],
        })

    if metadata.get("source_url"):
        cover_url = await fetch_cover_from_source_url(metadata["source_url"])
        if cover_url:
            add_candidate({
                "source": "source_url",
                "title": metadata.get("title", ""),
                "authors": authors,
                "score": 320,
                "size_name": "page",
                "url": cover_url,
            })

    if alias_entry.get("source_url") and alias_entry["source_url"] != metadata.get("source_url"):
        cover_url = await fetch_cover_from_source_url(alias_entry["source_url"])
        if cover_url:
            add_candidate({
                "source": "source_url",
                "title": metadata.get("title", ""),
                "authors": authors,
                "score": 310,
                "size_name": "page",
                "url": cover_url,
            })

    for candidate in await search_akniga_candidates(titles, authors):
        add_candidate(candidate)
    for candidate in await search_open_library_candidates(titles, authors):
        add_candidate(candidate)
    for candidate in await search_google_books_candidates(titles, authors):
        add_candidate(candidate)

    return candidates


async def process_file(file_name: str, aliases: dict) -> dict:
    base_name = os.path.splitext(file_name)[0]
    metadata = load_metadata(file_name)
    alias_entry = alias_entry_for(file_name, metadata, aliases)

    existing_cover = detect_existing_cover(base_name)
    if existing_cover:
        if metadata.get("local_cover") != existing_cover:
            metadata["local_cover"] = existing_cover
            if alias_entry.get("source_url") and not metadata.get("source_url"):
                metadata["source_url"] = alias_entry["source_url"]
            if metadata:
                save_metadata(file_name, metadata)
        return {"file": file_name, "status": "already_has_cover", "cover": existing_cover}

    raw_candidates = await find_cover_candidates(file_name, metadata, aliases)
    if not raw_candidates:
        return {"file": file_name, "status": "not_found"}

    checked_candidates = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        for candidate in raw_candidates:
            checked = await fetch_image_candidate(client, candidate)
            if checked:
                checked_candidates.append(checked)

    if not checked_candidates:
        return {
            "file": file_name,
            "status": "download_failed",
            "tried": [candidate["source"] for candidate in raw_candidates],
        }

    checked_candidates.sort(key=candidate_rank, reverse=True)
    best = checked_candidates[0]

    ext = resolve_cover_extension(best["url"], best["content_type"])
    cover_file_name = f"{base_name}{ext}"
    cover_path = os.path.join(config.DOWNLOADS_DIR, cover_file_name)
    async with aiofiles.open(cover_path, "wb") as f:
        await f.write(best["image_bytes"])

    metadata["title"] = metadata.get("title") or base_name
    metadata["file_name"] = metadata.get("file_name") or file_name
    if alias_entry.get("source_url") and not metadata.get("source_url"):
        metadata["source_url"] = alias_entry["source_url"]
    metadata["cover_url"] = best["url"]
    metadata["local_cover"] = cover_file_name
    save_metadata(file_name, metadata)

    return {
        "file": file_name,
        "status": "downloaded",
        "cover": cover_file_name,
        "cover_url": best["url"],
        "source": best["source"],
        "width": best["width"],
        "height": best["height"],
        "candidate_title": best["title"],
    }


async def main():
    aliases = await load_aliases()
    results = []
    await scraper.init_browser()
    try:
        for file_name in iter_audio_files():
            result = await process_file(file_name, aliases)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
    finally:
        await scraper.close_browser()

    summary = {
        "total": len(results),
        "downloaded": sum(1 for item in results if item["status"] == "downloaded"),
        "already_has_cover": sum(1 for item in results if item["status"] == "already_has_cover"),
        "not_found": sum(1 for item in results if item["status"] == "not_found"),
        "download_failed": sum(1 for item in results if item["status"] == "download_failed"),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
