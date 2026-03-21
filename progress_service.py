import json
import os
import threading
import time

from service_models import ProgressEntryModel


PROGRESS_STORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress_store.json")
PROGRESS_PERSIST_MIN_INTERVAL_SECONDS = 1.0
store_lock = threading.RLock()
terminal_progress_statuses = {"success", "error", "not_found", "interrupted"}
interrupted_task_message = "Task was interrupted by a server restart."
_progress_store_dirty = False
_last_persist_at = 0.0


def _write_progress_store_unlocked(now: float | None = None):
    global _progress_store_dirty, _last_persist_at
    temp_file = PROGRESS_STORE_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(progress_store, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, PROGRESS_STORE_FILE)
    _progress_store_dirty = False
    _last_persist_at = now if now is not None else time.time()


def _mark_progress_store_dirty():
    global _progress_store_dirty
    _progress_store_dirty = True


def _persist_progress_store_if_due():
    if not _progress_store_dirty:
        return False
    now = time.time()
    if now - _last_persist_at < PROGRESS_PERSIST_MIN_INTERVAL_SECONDS:
        return False
    _write_progress_store_unlocked(now)
    return True


def flush_progress_store(force: bool = False):
    if not force and not _progress_store_dirty:
        return False
    _write_progress_store_unlocked()
    return True


def _load_progress_store():
    if not os.path.exists(PROGRESS_STORE_FILE):
        return {}

    try:
        with open(PROGRESS_STORE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            normalized = {}
            for task_id, entry in payload.items():
                if not isinstance(entry, dict):
                    continue
                try:
                    normalized[task_id] = ProgressEntryModel.model_validate(entry).model_dump()
                except Exception:
                    continue
            return normalized
    except Exception:
        pass
    return {}


def _mark_inflight_tasks_interrupted():
    changed = False
    now = time.time()
    for entry in progress_store.values():
        if entry.get("status") in terminal_progress_statuses:
            continue
        entry["status"] = "interrupted"
        entry["phase"] = "interrupted"
        entry["message"] = interrupted_task_message
        entry["updated_at"] = now
        changed = True

    if changed:
        _mark_progress_store_dirty()
        flush_progress_store(force=True)


progress_store = _load_progress_store()
_mark_inflight_tasks_interrupted()


def create_progress_entry(source_url: str = "", mode: str = "") -> dict:
    return ProgressEntryModel(source_url=source_url, mode=mode).model_dump()


def get_progress(task_id: str) -> dict:
    with store_lock:
        _persist_progress_store_if_due()
        payload = progress_store.get(task_id)
        if payload is None:
            return {"status": "not_found"}
        return ProgressEntryModel.model_validate(payload).model_dump()


def set_progress(task_id: str, payload: dict):
    with store_lock:
        progress_store[task_id] = ProgressEntryModel.model_validate(payload).model_dump()
        _mark_progress_store_dirty()
        flush_progress_store(force=True)


def update_progress_entry(task_id: str, **fields):
    with store_lock:
        entry = progress_store.get(task_id)
        if entry is None:
            return None

        entry.update(fields)
        entry["updated_at"] = time.time()
        entry = ProgressEntryModel.model_validate(entry).model_dump()
        progress_store[task_id] = entry
        _mark_progress_store_dirty()
        if entry.get("status") in terminal_progress_statuses:
            flush_progress_store(force=True)
        else:
            _persist_progress_store_if_due()
        return dict(entry)


def cleanup_expired_progress(expire_seconds: int) -> list[str]:
    with store_lock:
        now = time.time()
        to_delete = [
            tid for tid, data in list(progress_store.items())
            if data.get("status") in terminal_progress_statuses
            and now - float(data.get("updated_at") or data.get("timestamp") or 0) > expire_seconds
        ]
        for tid in to_delete:
            del progress_store[tid]
        if to_delete:
            _mark_progress_store_dirty()
            flush_progress_store(force=True)
        return to_delete


def find_active_task_by_source(source_url: str):
    if not source_url:
        return None
    with store_lock:
        for task_id, data in progress_store.items():
            if data.get("source_url") != source_url:
                continue
            if data.get("status") in terminal_progress_statuses:
                continue
            return task_id, dict(data)
    return None


def count_active_tasks() -> int:
    with store_lock:
        return sum(
            1
            for data in progress_store.values()
            if data.get("status") not in terminal_progress_statuses
        )
