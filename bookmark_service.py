import copy
import hashlib
import json
import os
import re
import time

import config


BOOK_PREFIX = "book:"
BOOK_FILE_PREFIX = "book:file:"
STATE_DIR_NAME = ".sonicbook-state"
STATE_PROFILES_DIR_NAME = "profiles"
STATE_FILE_NAME = "playback_state.json"
LEGACY_MIGRATION_MARKER = ".profiles-migrated"
STATE_VERSION = 1
LEGACY_BOOKMARKS_FILE = os.path.join(config.BASE_DIR, "bookmarks.json")


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
    if not book_id or not book_id.startswith(BOOK_FILE_PREFIX):
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


def _shared_state_dir() -> str:
    return os.path.join(config.DOWNLOADS_DIR, STATE_DIR_NAME)


def _legacy_shared_state_file() -> str:
    return os.path.join(_shared_state_dir(), STATE_FILE_NAME)


def _legacy_migration_marker_file() -> str:
    return os.path.join(_shared_state_dir(), LEGACY_MIGRATION_MARKER)


def _active_profile_status() -> dict:
    return config.get_playback_profile_status()


def _profile_storage_slug(profile_id: str) -> str:
    normalized = str(profile_id or "").strip().lower()
    if not normalized:
        normalized = "device"
    safe = re.sub(r"[^a-z0-9._-]+", "-", normalized).strip("-.")
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    base = safe[:48].rstrip("-.") or "profile"
    return f"{base}-{digest}"


def _profile_state_dir(profile_id: str = "") -> str:
    active_profile_id = str(profile_id or _active_profile_status().get("profile_id") or "").strip()
    return os.path.join(_shared_state_dir(), STATE_PROFILES_DIR_NAME, _profile_storage_slug(active_profile_id))


def _shared_state_file() -> str:
    return os.path.join(_profile_state_dir(), STATE_FILE_NAME)



_state_cache = None
_state_cache_mtime = 0

def _copy_state(st: dict) -> dict:
    import copy
    return copy.deepcopy(st)



def _default_state() -> dict:
    return {
        "version": STATE_VERSION,
        "updated_at": 0,
        "bookmarks": {},
        "last_active": {},
    }


def _ensure_shared_state_dir() -> str:
    state_dir = _profile_state_dir()
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


def get_state_storage_status() -> dict:
    profile = _active_profile_status()
    return {
        "profile_id": profile.get("profile_id", ""),
        "configured_id": profile.get("configured_id", ""),
        "source": profile.get("source", "device"),
        "state_file": _shared_state_file(),
        "legacy_state_file": _legacy_shared_state_file(),
    }


def _load_json_file(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_marker_file(path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass


def _normalize_last_active(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}

    source = str(payload.get("source") or "").strip()
    normalized = {
        "book_id": str(payload.get("book_id") or "").strip(),
        "file_name": str(payload.get("file_name") or "").strip(),
        "source": source,
        "drive_file_id": str(payload.get("drive_file_id") or "").strip(),
        "drive_metadata_file_id": str(payload.get("drive_metadata_file_id") or "").strip(),
        "drive_cover_file_id": str(payload.get("drive_cover_file_id") or "").strip(),
        "drive_resource_key": str(payload.get("drive_resource_key") or "").strip(),
        "drive_metadata_resource_key": str(payload.get("drive_metadata_resource_key") or "").strip(),
        "drive_cover_resource_key": str(payload.get("drive_cover_resource_key") or "").strip(),
        "size_bytes": int(payload.get("size_bytes") or 0),
        "updated_at": float(payload.get("updated_at") or 0),
    }
    if not normalized["book_id"] and not normalized["file_name"] and not normalized["drive_file_id"]:
        return {}
    return normalized


def _normalize_state_payload(payload) -> dict:
    state = _default_state()
    if not isinstance(payload, dict):
        return state

    # Legacy flat payload: {book_id: {...bookmark...}}
    if "bookmarks" not in payload and all(isinstance(value, dict) for value in payload.values()):
        state["bookmarks"] = payload
        return state

    bookmarks = payload.get("bookmarks")
    if isinstance(bookmarks, dict):
        state["bookmarks"] = bookmarks
    state["updated_at"] = float(payload.get("updated_at") or 0)
    state["last_active"] = _normalize_last_active(payload.get("last_active"))
    return state


def _save_state(state: dict) -> bool:
    global _state_cache, _state_cache_mtime
    state_path = _shared_state_file()
    with config.locked_json_file(state_path):
        temp_path = state_path + ".tmp"
        payload = {
            "version": STATE_VERSION,
            "updated_at": time.time(),
            "bookmarks": state.get("bookmarks", {}),
            "last_active": _normalize_last_active(state.get("last_active")),
        }
        try:
            _ensure_shared_state_dir()
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, state_path)

            # Invalidate cache locally
            try:
                _state_cache_mtime = os.path.getmtime(state_path)
            except OSError:
                _state_cache_mtime = 0
            _state_cache = _copy_state(payload)

            return True
        except (OSError, TypeError, ValueError):
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False


def _migrate_legacy_bookmarks_if_needed() -> dict | None:
    state_path = _shared_state_file()
    if os.path.exists(state_path):
        return None

    marker_path = _legacy_migration_marker_file()
    if not os.path.exists(marker_path):
        legacy_shared_payload = _load_json_file(_legacy_shared_state_file())
        if isinstance(legacy_shared_payload, dict):
            migrated_state = _normalize_state_payload(legacy_shared_payload)
            _save_state(migrated_state)
            _write_marker_file(marker_path)
            return migrated_state

    legacy_payload = _load_json_file(LEGACY_BOOKMARKS_FILE)
    if not isinstance(legacy_payload, dict):
        return None

    migrated_state = _default_state()
    migrated_state["bookmarks"] = legacy_payload
    _save_state(migrated_state)
    _write_marker_file(marker_path)
    return migrated_state


def load_state() -> dict:
    global _state_cache, _state_cache_mtime
    with config.locked_json_file(_shared_state_file()):
        migrated_state = _migrate_legacy_bookmarks_if_needed()
        if migrated_state is not None:
            # If a migration just occurred, don't use cache, normalize and return directly
            state = _normalize_state_payload(migrated_state)
            _state_cache = _copy_state(state)
            state_file = _shared_state_file()
            try:
                _state_cache_mtime = os.path.getmtime(state_file)
            except OSError:
                _state_cache_mtime = 0
            return _copy_state(state)

        state_file = _shared_state_file()
        try:
            mtime = os.path.getmtime(state_file)
        except OSError:
            mtime = 0

        if _state_cache is not None and mtime > 0 and _state_cache_mtime == mtime:
            return _copy_state(_state_cache)

        raw_state = _load_json_file(state_file)
        state = _normalize_state_payload(raw_state)
        _state_cache = _copy_state(state)
        _state_cache_mtime = mtime
        return _copy_state(state)


def load_bookmarks() -> dict:
    return load_state().get("bookmarks", {})


def save_bookmarks(bookmarks: dict) -> bool:
    with config.locked_json_file(_shared_state_file()):
        state = load_state()
        state["bookmarks"] = bookmarks if isinstance(bookmarks, dict) else {}
        return _save_state(state)


def get_bookmark(book_id: str) -> dict | None:
    bookmarks = load_bookmarks()
    for candidate_id in build_book_id_aliases(book_id=book_id):
        bookmark = bookmarks.get(candidate_id)
        if isinstance(bookmark, dict):
            return copy.deepcopy(bookmark)
    return None


def list_bookmarks() -> dict:
    return load_bookmarks()


def get_last_active() -> dict:
    return copy.deepcopy(load_state().get("last_active") or {})


def save_last_active(payload: dict) -> dict:
    normalized = _normalize_last_active(payload)
    if not normalized:
        raise RuntimeError("Missing active playback payload.")

    if not normalized["updated_at"]:
        normalized["updated_at"] = time.time()

    with config.locked_json_file(_shared_state_file()):
        state = load_state()
        state["last_active"] = normalized
        if not _save_state(state):
            raise RuntimeError("Failed to persist last active playback.")
        return copy.deepcopy(normalized)


def clear_last_active() -> bool:
    with config.locked_json_file(_shared_state_file()):
        state = load_state()
        state["last_active"] = {}
        return _save_state(state)


def save_bookmark(book_id: str, payload: dict) -> dict:
    if not book_id:
        raise RuntimeError("Missing book ID.")

    time_value = float(payload.get("time") or 0)
    duration_value = float(payload.get("duration") or 0)
    track_value = int(payload.get("track") or 0)
    completed_value = payload.get("completed")
    if duration_value < 0:
        duration_value = 0
    if time_value < 0:
        time_value = 0
    if duration_value > 0:
        time_value = min(time_value, duration_value)

    if isinstance(completed_value, str):
        lowered = completed_value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            completed_value = True
        elif lowered in {"0", "false", "no", "off"}:
            completed_value = False
        else:
            completed_value = None
    elif completed_value is not None:
        completed_value = bool(completed_value)

    derived_completed = duration_value > 0 and (time_value / duration_value) >= 0.995
    completed_flag = completed_value if isinstance(completed_value, bool) else derived_completed

    with config.locked_json_file(_shared_state_file()):
        bookmarks = load_bookmarks()
        aliases = build_book_id_aliases(book_id=book_id)
        if book_id not in bookmarks:
            for alias in aliases:
                if alias != book_id and isinstance(bookmarks.get(alias), dict):
                    bookmarks[book_id] = bookmarks[alias]
                    del bookmarks[alias]
                    break

        bookmark = {
            "time": round(time_value, 3),
            "duration": round(duration_value, 3),
            "track": max(0, track_value),
            "file_name": payload.get("file_name", ""),
            "source": payload.get("source", ""),
            "completed": completed_flag,
            "updated_at": time.time(),
        }
        bookmarks[book_id] = bookmark

        state = load_state()
        state["bookmarks"] = bookmarks
        if not _save_state(state):
            raise RuntimeError("Failed to persist bookmark.")
        return copy.deepcopy(bookmark)


def delete_bookmark(book_id: str) -> bool:
    if not book_id:
        return False

    with config.locked_json_file(_shared_state_file()):
        state = load_state()
        bookmarks = state.get("bookmarks", {})
        changed = False
        for candidate_id in build_book_id_aliases(book_id=book_id):
            if candidate_id in bookmarks:
                del bookmarks[candidate_id]
                changed = True

        last_active = state.get("last_active") or {}
        if last_active:
            active_book_id = str(last_active.get("book_id") or "").strip()
            if active_book_id and active_book_id in build_book_id_aliases(book_id=book_id):
                state["last_active"] = {}
                changed = True

        if not changed:
            return True

        state["bookmarks"] = bookmarks
        return _save_state(state)
