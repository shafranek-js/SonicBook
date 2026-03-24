import asyncio
import os
import zipfile

from fastapi import HTTPException

import library_service


zip_extraction_locks = {}


def get_zip_extraction_lock(extract_dir_name: str) -> asyncio.Lock:
    lock = zip_extraction_locks.get(extract_dir_name)
    if lock is None:
        lock = asyncio.Lock()
        zip_extraction_locks[extract_dir_name] = lock
    return lock


def extract_zip_archive(zip_path: str, extract_dir_path: str):
    with zipfile.ZipFile(zip_path, "r") as archive:
        # Prevent Zip Slip vulnerability (path traversal)
        # by verifying that all members are within the destination directory.
        resolved_extract_dir = os.path.abspath(extract_dir_path)
        for member in archive.infolist():
            target_path = os.path.abspath(os.path.join(resolved_extract_dir, member.filename))
            if not target_path.startswith(resolved_extract_dir + os.sep) and target_path != resolved_extract_dir:
                raise ValueError(f"Malicious member path detected: {member.filename}")

        archive.extractall(extract_dir_path)


async def ensure_zip_extracted(zip_path: str, extract_dir_name: str, extract_dir_path: str):
    if os.path.exists(extract_dir_path):
        return

    lock = get_zip_extraction_lock(extract_dir_name)
    async with lock:
        if os.path.exists(extract_dir_path):
            return

        try:
            await asyncio.to_thread(extract_zip_archive, zip_path, extract_dir_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to extract ZIP for playback") from exc


async def build_zip_metadata(file_path: str, file_name: str, downloads_dir: str) -> dict:
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ZIP file not found")

    extract_dir_name = f".extracted_{base_name}"
    extract_dir_path = os.path.join(downloads_dir, extract_dir_name)
    await ensure_zip_extracted(file_path, extract_dir_name, extract_dir_path)

    playlist = []
    if os.path.exists(extract_dir_path):
        for name in sorted(os.listdir(extract_dir_path)):
            if name.endswith((".mp3", ".m4a", ".mp4")):
                playlist.append({
                    "title": os.path.splitext(name)[0],
                    "file": f"{extract_dir_name}/{name}"
                })

    payload = {
        "title": base_name,
        "mode": "zip",
        "playlist": playlist
    }
    sidecar_meta = library_service.load_sidecar_metadata(file_path)
    if sidecar_meta:
        payload["title"] = sidecar_meta.get("title") or payload["title"]
        payload["cover_url"] = sidecar_meta.get("cover_url")
        payload["local_cover"] = sidecar_meta.get("local_cover")
        payload["file_name"] = sidecar_meta.get("file_name", file_name)

    return payload
