import copy
import json
import os
import re
import time

import config
from json_storage import locked_json_path, read_json_unlocked, write_json_unlocked
from service_models import BookmarkRecordModel


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
    with locked_json_path(BOOKMARKS_FILE):
        return _load_bookmarks_unlocked()


def _load_bookmarks_unlocked() -> dict:
    if not os.path.exists(BOOKMARKS_FILE):
        return {}
    try:
        data = read_json_unlocked(BOOKMARKS_FILE, default={})
        if not isinstance(data, dict):
            return {}
        normalized = {}
        for book_id, payload in data.items():
            if not isinstance(payload, dict):
                continue
            try:
                normalized[book_id] = BookmarkRecordModel.model_validate(payload).model_dump()
            except Exception:
                continue
        return normalized
    except Exception:
        return {}


def save_bookmarks(bookmarks: dict) -> bool:
    with locked_json_path(BOOKMARKS_FILE):
        return _save_bookmarks_unlocked(bookmarks)


def _save_bookmarks_unlocked(bookmarks: dict) -> bool:
    temp_path = BOOKMARKS_FILE + ".tmp"
    try:
        write_json_unlocked(BOOKMARKS_FILE, bookmarks)
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
    with locked_json_path(BOOKMARKS_FILE):
        bookmarks = _load_bookmarks_unlocked()
        aliases = build_book_id_aliases(book_id=book_id)
        if book_id not in bookmarks:
            for alias in aliases:
                if alias != book_id and isinstance(bookmarks.get(alias), dict):
                    bookmarks[book_id] = bookmarks[alias]
                    del bookmarks[alias]
                    break
        bookmarks[book_id] = BookmarkRecordModel(
            time=payload.get("time"),
            duration=payload.get("duration"),
            track=payload.get("track"),
            file_name=payload.get("file_name", ""),
            source=payload.get("source", ""),
            updated_at=time.time(),
        ).model_dump()
        if not _save_bookmarks_unlocked(bookmarks):
            raise RuntimeError("Failed to persist bookmark.")
        return copy.deepcopy(bookmarks[book_id])


def delete_bookmark(book_id: str) -> bool:
    if not book_id:
        return False
    with locked_json_path(BOOKMARKS_FILE):
        bookmarks = _load_bookmarks_unlocked()
        changed = False
        for candidate_id in build_book_id_aliases(book_id=book_id):
            if candidate_id in bookmarks:
                del bookmarks[candidate_id]
                changed = True
        if not changed:
            return True
        return _save_bookmarks_unlocked(bookmarks)
