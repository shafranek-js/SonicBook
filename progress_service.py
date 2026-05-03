import atexit
import json
import logging
import os
import time
import copy
import threading

import config

logger = logging.getLogger(__name__)
progress_store = {}
terminal_progress_statuses = {"success", "error", "not_found"}
_progress_lock = threading.RLock()
PROGRESS_STORE_FILE = os.path.join(config.BASE_DIR, "progress_store.json")
PROGRESS_STORE_FILE_VERSION = 1
PROGRESS_STORE_FLUSH_INTERVAL_SECONDS = 1.0
_progress_store_dirty = False
_progress_store_last_flush_at = 0.0


def _normalize_progress_payload(payload) -> dict:
    if not isinstance(payload, dict):
        return {}
    tasks = payload.get("tasks", payload)
    if not isinstance(tasks, dict):
        return {}
    normalized = {}
    for task_id, task_payload in tasks.items():
        if isinstance(task_payload, dict):
            normalized[str(task_id)] = copy.deepcopy(task_payload)
    return normalized


def _load_progress_store_from_disk() -> dict:
    with config.locked_json_file(PROGRESS_STORE_FILE):
        if not os.path.exists(PROGRESS_STORE_FILE):
            return {}
        try:
            with open(PROGRESS_STORE_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return _normalize_progress_payload(payload)
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load persisted progress store", exc_info=True)
            return {}


def _write_progress_store_snapshot(snapshot: dict) -> bool:
    with config.locked_json_file(PROGRESS_STORE_FILE):
        temp_path = PROGRESS_STORE_FILE + ".tmp"
        payload = {
            "version": PROGRESS_STORE_FILE_VERSION,
            "updated_at": time.time(),
            "tasks": snapshot,
        }
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, PROGRESS_STORE_FILE)
            return True
        except (OSError, TypeError, ValueError):
            logger.warning("Failed to persist progress store", exc_info=True)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False


def _flush_progress_store(force: bool = False) -> bool:
    global _progress_store_dirty, _progress_store_last_flush_at
    with _progress_lock:
        if not _progress_store_dirty:
            return True

        now_ts = time.time()
        if not force and (now_ts - _progress_store_last_flush_at) < PROGRESS_STORE_FLUSH_INTERVAL_SECONDS:
            return False

        snapshot = copy.deepcopy(progress_store)

    if _write_progress_store_snapshot(snapshot):
        with _progress_lock:
            _progress_store_last_flush_at = now_ts
            _progress_store_dirty = False
        return True

    return False


def _mark_progress_dirty(force_flush: bool = False):
    global _progress_store_dirty
    with _progress_lock:
        _progress_store_dirty = True
    _flush_progress_store(force=force_flush)


def _should_force_flush_for_status(status_value) -> bool:
    return str(status_value or "").strip().lower() in terminal_progress_statuses


def _flush_progress_on_exit():
    _flush_progress_store(force=True)


progress_store = _load_progress_store_from_disk()
atexit.register(_flush_progress_on_exit)


def create_progress_entry(source_url: str = "", mode: str = "") -> dict:
    return {
        "status": "searching",
        "phase": "searching",
        "percent": 0.0,
        "current_frag": 0,
        "total_frags": 0,
        "file_name": "",
        "source_url": source_url,
        "mode": mode,
        "timestamp": time.time()
    }


def get_progress(task_id: str) -> dict:
    with _progress_lock:
        entry = progress_store.get(task_id, {"status": "not_found"})
        return copy.deepcopy(entry)


def set_progress(task_id: str, payload: dict):
    with _progress_lock:
        progress_store[task_id] = copy.deepcopy(payload)
    force_flush = _should_force_flush_for_status((payload or {}).get("status"))
    _mark_progress_dirty(force_flush=force_flush)


def update_progress_entry(task_id: str, **fields):
    with _progress_lock:
        entry = progress_store.get(task_id)
        if entry is None:
            return None

        entry.update(copy.deepcopy(fields))
        entry["timestamp"] = time.time()
        updated = copy.deepcopy(entry)

    force_flush = _should_force_flush_for_status(fields.get("status"))
    _mark_progress_dirty(force_flush=force_flush)
    return updated


def cleanup_expired_progress(expire_seconds: int) -> list[str]:
    with _progress_lock:
        now = time.time()
        to_delete = [
            tid for tid, data in list(progress_store.items())
            if data.get("status") in terminal_progress_statuses
            and now - data.get("timestamp", 0) > expire_seconds
        ]
        for tid in to_delete:
            del progress_store[tid]

    if to_delete:
        _mark_progress_dirty(force_flush=True)
    return to_delete


def find_active_task_by_source(source_url: str):
    if not source_url:
        return None
    with _progress_lock:
        for task_id, data in progress_store.items():
            if data.get("source_url") != source_url:
                continue
            if data.get("status") in terminal_progress_statuses:
                continue
            return task_id, copy.deepcopy(data)
        return None
