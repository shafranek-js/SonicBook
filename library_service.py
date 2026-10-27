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
    except (subprocess.TimeoutExpired, OSError, ValueError):
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
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read sidecar metadata: %s", json_path)
        return None


def load_sidecar_metadata(file_path: str) -> dict | None:
    return load_sidecar_metadata_from_path(_sidecar_json_path(file_path))


def _load_library_index() -> dict:
    with config.locked_json_file(LIBRARY_INDEX_FILE):
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
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.exception("Failed to read library index: %s", LIBRARY_INDEX_FILE)
            return {"version": LIBRARY_INDEX_VERSION, "entries": {}}


def _save_library_index(entries: dict):
    with config.locked_json_file(LIBRARY_INDEX_FILE):
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
        except (OSError, TypeError, ValueError):
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
    audio_entries = []
    sidecar_entries = {}

    with os.scandir(downloads_dir) as iterator:
        for entry in iterator:
            if not entry.is_file():
                continue
            name = entry.name
            if name.endswith(AUDIO_EXTENSIONS):
                audio_entries.append(entry)
            elif name.endswith(".json"):
                sidecar_entries[name] = entry

    for entry in audio_entries:
        stat = entry.stat()
        size_bytes = stat.st_size
        mtime = stat.st_mtime
        mtime_ns = stat.st_mtime_ns
        sidecar_path = _sidecar_json_path(entry.path)
        sidecar_name = os.path.basename(sidecar_path)
        sidecar_entry = sidecar_entries.get(sidecar_name)
        sidecar_mtime_ns = sidecar_entry.stat().st_mtime_ns if sidecar_entry else 0

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


def delete_library_book(file_name: str, downloads_dir: str | None = None) -> dict:
    if not file_name:
        raise ValueError("Invalid file name")

    target_dir = os.path.abspath(downloads_dir or config.DOWNLOADS_DIR)
    normalized_name = os.path.normpath(file_name)
    drive, _ = os.path.splitdrive(normalized_name)
    if drive or os.path.isabs(file_name) or os.path.isabs(normalized_name):
        raise ValueError("Invalid file path")

    candidate_path = os.path.abspath(os.path.join(target_dir, normalized_name))
    try:
        if os.path.commonpath([target_dir, candidate_path]) != target_dir:
            raise ValueError("Path outside library directory")
    except ValueError as exc:
        raise ValueError("Invalid file path") from exc

    if not os.path.exists(candidate_path):
        raise FileNotFoundError(f"File not found: {file_name}")

    base_name = os.path.splitext(os.path.basename(candidate_path))[0]
    sidecar_path = _sidecar_json_path(candidate_path)
    entry_key = os.path.basename(candidate_path)

    # 1. Load sidecar metadata if present to extract cover and aliases
    sidecar_meta = load_sidecar_metadata_from_path(sidecar_path)
    size_bytes = os.path.getsize(candidate_path) if os.path.isfile(candidate_path) else 0

    # 2. Collect files to delete
    files_to_delete = [candidate_path]
    if os.path.exists(sidecar_path):
        files_to_delete.append(sidecar_path)

    # Check for local cover specified in sidecar metadata
    if sidecar_meta and isinstance(sidecar_meta.get("local_cover"), str):
        local_cover = sidecar_meta["local_cover"].strip()
        if local_cover:
            norm_cover = os.path.normpath(local_cover)
            cov_drive, _ = os.path.splitdrive(norm_cover)
            if not cov_drive and not os.path.isabs(norm_cover):
                cov_path = os.path.abspath(os.path.join(target_dir, norm_cover))
                try:
                    if os.path.commonpath([target_dir, cov_path]) == target_dir and os.path.exists(cov_path):
                        if cov_path not in files_to_delete:
                            files_to_delete.append(cov_path)
                except ValueError:
                    pass

    # Check for standard cover files based on base_name
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cand_cov = os.path.join(target_dir, f"{base_name}{ext}")
        if os.path.exists(cand_cov) and cand_cov not in files_to_delete:
            files_to_delete.append(cand_cov)

    # Check for partial download file (.part)
    part_path = f"{candidate_path}.part"
    if os.path.exists(part_path) and part_path not in files_to_delete:
        files_to_delete.append(part_path)

    # 3. Delete files safely
    deleted_files = []
    for path in files_to_delete:
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            deleted_files.append(os.path.basename(path))
        except OSError:
            logger.exception("Failed to delete file: %s", path)

    # 4. Remove from library index
    cached_index = _load_library_index()
    entries = cached_index.get("entries", {})
    if entry_key in entries:
        del entries[entry_key]
        _save_library_index(entries)

    # 5. Remove bookmarks and clear last_active
    book_id_aliases = bookmark_service.build_book_id_aliases(
        name=entry_key,
        size_bytes=size_bytes,
        metadata=sidecar_meta,
    )
    for alias in book_id_aliases:
        bookmark_service.delete_bookmark(alias)

    return {
        "status": "success",
        "file_name": entry_key,
        "deleted_files": deleted_files,
    }
