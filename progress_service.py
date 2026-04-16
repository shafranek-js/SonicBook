import time
import copy

progress_store = {}
terminal_progress_statuses = {"success", "error", "not_found"}


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
    result = progress_store.get(task_id)
    if result is None:
        return {"status": "not_found"}
    return copy.deepcopy(result)


def set_progress(task_id: str, payload: dict):
    progress_store[task_id] = copy.deepcopy(payload)


def update_progress_entry(task_id: str, **fields):
    entry = progress_store.get(task_id)
    if entry is None:
        return None

    entry.update(fields)
    entry["timestamp"] = time.time()
    return copy.deepcopy(entry)


def cleanup_expired_progress(expire_seconds: int) -> list[str]:
    now = time.time()
    to_delete = [
        tid for tid, data in list(progress_store.items())
        if data.get("status") in terminal_progress_statuses
        and now - data.get("timestamp", 0) > expire_seconds
    ]
    for tid in to_delete:
        del progress_store[tid]
    return to_delete


def find_active_task_by_source(source_url: str):
    if not source_url:
        return None
    for task_id, data in progress_store.items():
        if data.get("source_url") != source_url:
            continue
        if data.get("status") in terminal_progress_statuses:
            continue
        return task_id, copy.deepcopy(data)
    return None
