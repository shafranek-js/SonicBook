import json
import logging
import os
import subprocess

import config

logger = logging.getLogger(__name__)


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


def load_sidecar_metadata(file_path: str) -> dict | None:
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read sidecar metadata: %s", json_path)
        return None


def list_library_files(downloads_dir: str) -> list[dict]:
    if not os.path.exists(downloads_dir):
        return []

    files = []
    for name in os.listdir(downloads_dir):
        if not name.endswith(('.m4b', '.mp3', '.zip', '.mp4', '.m4a')):
            continue

        file_path = os.path.join(downloads_dir, name)
        size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        sidecar_meta = load_sidecar_metadata(file_path)
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

        files.append({
            "name": name,
            "size_mb": size_mb,
            "has_meta": has_meta,
            "duration_seconds": duration_seconds,
            "chapter_count": chapter_count,
            "mtime": os.path.getmtime(file_path)
        })

    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files
