import json
import logging
import os
import subprocess
import time

import bookmark_service
import config

logger = logging.getLogger(__name__)
AUDIO_EXTENSIONS = ('.m4b', '.mp3', '.zip', '.mp4', '.m4a')
LIBRARY_INDEX_FILE = os.path.join(config.BASE_DIR, "library_index.json")
LIBRARY_INDEX_VERSION = 1


def get_file_duration_seconds(file_path: str):
    if not os.path.exists(file_path) or file_path.endswith(".zip"):
        return None
    try:
        result = subprocess.run(
            [
                config.FFPROBE_PATH,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            check=False,
        )
        if result.returncode != 0:
            return None
        duration = float((result.stdout or "").strip() or 0)
        return round(duration, 2) if duration > 0 else None
    except Exception:
        return None


def _sidecar_json_path(file_path: str) -> str:
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    return os.path.join(os.path.dirname(file_path), f"{base_name}.json")


def load_sidecar_metadata_from_path(json_path: str) -> dict | None:
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read sidecar metadata: %s", json_path)
        return None


def load_sidecar_metadata(file_path: str) -> dict | None:
    return load_sidecar_metadata_from_path(_sidecar_json_path(file_path))


def _load_library_index() -> dict:
    if not os.path.exists(LIBRARY_INDEX_FILE):
        return {"version": LIBRARY_INDEX_VERSION, "entries": {}}
    try:
        with open(LIBRARY_INDEX_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return {"version": LIBRARY_INDEX_VERSION, "entries": {}}
        if int(payload.get("version") or 0) != LIBRARY_INDEX_VERSION:
            return {"version": LIBRARY_INDEX_VERSION, "entries": {}}
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return {"version": LIBRARY_INDEX_VERSION, "entries": {}}
        return {"version": LIBRARY_INDEX_VERSION, "entries": entries}
    except Exception:
        logger.exception("Failed to read library index: %s", LIBRARY_INDEX_FILE)
        return {"version": LIBRARY_INDEX_VERSION, "entries": {}}


def _save_library_index(entries: dict):
    temp_path = LIBRARY_INDEX_FILE + ".tmp"
    payload = {
        "version": LIBRARY_INDEX_VERSION,
        "updated_at": time.time(),
        "entries": entries,
    }
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, LIBRARY_INDEX_FILE)
    except Exception:
        logger.exception("Failed to write library index: %s", LIBRARY_INDEX_FILE)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _build_file_record(name: str, file_path: str, size_bytes: int, mtime: float, sidecar_meta: dict | None):
    size_mb = round(size_bytes / (1024 * 1024), 2)
    has_meta = sidecar_meta is not None
    duration_seconds = None
    chapter_count = None

    if sidecar_meta:
        chapters = sidecar_meta.get("chapters") or []
        if chapters:
            chapter_count = len(chapters)
            last_chapter = chapters[-1]
            duration_seconds = float(last_chapter.get("end") or 0) or None

    if not duration_seconds:
        duration_seconds = get_file_duration_seconds(file_path)

    return {
        "name": name,
        "book_id": bookmark_service.build_book_id(name, size_bytes=size_bytes, metadata=sidecar_meta),
        "size_bytes": size_bytes,
        "size_mb": size_mb,
        "has_meta": has_meta,
        "duration_seconds": duration_seconds,
        "chapter_count": chapter_count,
        "mtime": mtime,
    }


def _scan_library(downloads_dir: str) -> list[dict]:
    if not os.path.exists(downloads_dir):
        return []

    cached_index = _load_library_index()
    cached_entries = cached_index.get("entries", {})
    next_entries = {}
    files = []
    changed = False

    with os.scandir(downloads_dir) as iterator:
        for entry in iterator:
            if not entry.is_file() or not entry.name.endswith(AUDIO_EXTENSIONS):
                continue

            stat = entry.stat()
            size_bytes = stat.st_size
            mtime = stat.st_mtime
            mtime_ns = stat.st_mtime_ns
            sidecar_path = _sidecar_json_path(entry.path)
            sidecar_mtime_ns = 0
            if os.path.exists(sidecar_path):
                sidecar_mtime_ns = os.stat(sidecar_path).st_mtime_ns

            cached = cached_entries.get(entry.name)
            cached_file = cached.get("file") if isinstance(cached, dict) else None
            cache_hit = (
                isinstance(cached, dict)
                and isinstance(cached_file, dict)
                and int(cached.get("size_bytes") or 0) == size_bytes
                and int(cached.get("mtime_ns") or 0) == mtime_ns
                and int(cached.get("sidecar_mtime_ns") or 0) == sidecar_mtime_ns
            )

            if cache_hit:
                file_record = dict(cached_file)
            else:
                sidecar_meta = load_sidecar_metadata_from_path(sidecar_path) if sidecar_mtime_ns else None
                file_record = _build_file_record(entry.name, entry.path, size_bytes, mtime, sidecar_meta)
                changed = True

            next_entries[entry.name] = {
                "size_bytes": size_bytes,
                "mtime_ns": mtime_ns,
                "sidecar_mtime_ns": sidecar_mtime_ns,
                "file": file_record,
            }
            files.append(file_record)

    if set(cached_entries.keys()) != set(next_entries.keys()):
        changed = True
    if changed:
        _save_library_index(next_entries)
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


def list_library_files(downloads_dir: str) -> list[dict]:
    return _scan_library(downloads_dir)


def list_library_book_ids(downloads_dir: str) -> list[str]:
    book_ids = []
    seen = set()

    for item in _scan_library(downloads_dir):
        name = item.get("name", "")
        size_bytes = int(item.get("size_bytes") or 0)

        candidates = bookmark_service.build_book_id_aliases(
            name=name,
            size_bytes=size_bytes,
            book_id=item.get("book_id", ""),
        )

        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                book_ids.append(candidate)

    return book_ids
