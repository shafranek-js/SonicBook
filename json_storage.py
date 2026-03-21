import json
import os
import threading
from contextlib import contextmanager


_registry_lock = threading.Lock()
_file_locks: dict[str, threading.RLock] = {}


def _normalize_path(path: str) -> str:
    return os.path.abspath(path)


def get_json_lock(path: str) -> threading.RLock:
    normalized = _normalize_path(path)
    with _registry_lock:
        lock = _file_locks.get(normalized)
        if lock is None:
            lock = threading.RLock()
            _file_locks[normalized] = lock
        return lock


@contextmanager
def locked_json_path(path: str):
    lock = get_json_lock(path)
    with lock:
        yield


def read_json_unlocked(path: str, *, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_unlocked(path: str, payload) -> None:
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)
