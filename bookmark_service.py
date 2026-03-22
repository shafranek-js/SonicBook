import copy
import json
import os
import re
import time

import config


BOOKMARKS_FILE = os.path.join(config.BASE_DIR, "bookmarks.json")
BOOK_PREFIX = "book:"
BOOK_FILE_PREFIX = "book:file:"


def _normalize_book_name(name: str) -> str:
    base = os.path.splitext(os.path.basename(name or ""))[0]
    normalized = re.sub(r"[^\w]+", " ", base.lower(), flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", normalized, flags=re.UNICODE)


def _resolve_identity_name(name: str = "", metadata: dict | None = None) -> str:
    metadata = metadata or {}
    return str(
        metadata.get("file_name")
        or name
        or metadata.get("title")
        or ""
    )


def build_legacy_book_id(name: str = "", metadata: dict | None = None) -> str:
    normalized = _normalize_book_name(_resolve_identity_name(name, metadata))
    if not normalized:
        return ""
    return f"{BOOK_PREFIX}{normalized}"


def build_book_id(name: str = "", size_bytes: int | None = None, metadata: dict | None = None) -> str:
    normalized = _normalize_book_name(_resolve_identity_name(name, metadata))
    if not normalized:
        return ""
    safe_size = int(size_bytes or 0)
    if safe_size > 0:
        return f"{BOOK_FILE_PREFIX}{normalized}:{safe_size}"
    return f"{BOOK_FILE_PREFIX}{normalized}"


def _derive_aliases_from_book_id(book_id: str) -> list[str]:
    if not book_id:
        return []
    if not book_id.startswith(BOOK_FILE_PREFIX):
        return []

    suffix = book_id[len(BOOK_FILE_PREFIX):]
    normalized = suffix
    if ":" in suffix:
        maybe_name, maybe_size = suffix.rsplit(":", 1)
        if maybe_size.isdigit():
            normalized = maybe_name

    aliases = [f"{BOOK_PREFIX}{normalized}"]
    unsized = f"{BOOK_FILE_PREFIX}{normalized}"
    if unsized != book_id:
        aliases.append(unsized)
    return aliases


def build_book_id_aliases(name: str = "", size_bytes: int | None = None, metadata: dict | None = None, book_id: str = "") -> list[str]:
    aliases = []
    if book_id:
        aliases.append(book_id)
        aliases.extend(_derive_aliases_from_book_id(book_id))
    else:
        canonical = build_book_id(name, size_bytes=size_bytes, metadata=metadata)
        if canonical:
            aliases.append(canonical)
            aliases.extend(_derive_aliases_from_book_id(canonical))
    legacy = build_legacy_book_id(name, metadata=metadata)
    if legacy:
        aliases.append(legacy)

    deduped = []
    seen = set()
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            deduped.append(alias)
    return deduped


def load_bookmarks() -> dict:
    if not os.path.exists(BOOKMARKS_FILE):
        return {}
    try:
        with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_bookmarks(bookmarks: dict) -> bool:
    temp_path = BOOKMARKS_FILE + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, BOOKMARKS_FILE)
        return True
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return False


def get_bookmark(book_id: str) -> dict | None:
    bookmarks = load_bookmarks()
    for candidate_id in build_book_id_aliases(book_id=book_id):
        bookmark = bookmarks.get(candidate_id)
        if isinstance(bookmark, dict):
            return copy.deepcopy(bookmark)
    return None


def list_bookmarks() -> dict:
    return load_bookmarks()


def save_bookmark(book_id: str, payload: dict) -> dict:
    if not book_id:
        raise RuntimeError("Missing book ID.")

    time_value = float(payload.get("time") or 0)
    duration_value = float(payload.get("duration") or 0)
    track_value = int(payload.get("track") or 0)
    if duration_value < 0:
        duration_value = 0
    if time_value < 0:
        time_value = 0
    if duration_value > 0:
        time_value = min(time_value, duration_value)

    bookmarks = load_bookmarks()
    aliases = build_book_id_aliases(book_id=book_id)
    if book_id not in bookmarks:
        for alias in aliases:
            if alias != book_id and isinstance(bookmarks.get(alias), dict):
                bookmarks[book_id] = bookmarks[alias]
                del bookmarks[alias]
                break
    bookmarks[book_id] = {
        "time": round(time_value, 3),
        "duration": round(duration_value, 3),
        "track": max(0, track_value),
        "file_name": payload.get("file_name", ""),
        "source": payload.get("source", ""),
        "updated_at": time.time(),
    }
    if not save_bookmarks(bookmarks):
        raise RuntimeError("Failed to persist bookmark.")
    return copy.deepcopy(bookmarks[book_id])


def delete_bookmark(book_id: str) -> bool:
    if not book_id:
        return False
    bookmarks = load_bookmarks()
    changed = False
    for candidate_id in build_book_id_aliases(book_id=book_id):
        if candidate_id in bookmarks:
            del bookmarks[candidate_id]
            changed = True
    if not changed:
        return True
    return save_bookmarks(bookmarks)
