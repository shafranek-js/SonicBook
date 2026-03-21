import asyncio
import os
import zipfile

from fastapi import HTTPException

import library_service


zip_extraction_locks = {}
MAX_ZIP_MEMBERS = 2000
MAX_ZIP_UNCOMPRESSED_BYTES = 20 * 1024 * 1024 * 1024
MAX_SINGLE_ZIP_ENTRY_BYTES = 2 * 1024 * 1024 * 1024


class UnsafeZipArchiveError(RuntimeError):
    pass


def get_zip_extraction_lock(extract_dir_name: str) -> asyncio.Lock:
    lock = zip_extraction_locks.get(extract_dir_name)
    if lock is None:
        lock = asyncio.Lock()
        zip_extraction_locks[extract_dir_name] = lock
    return lock


def _is_zip_symlink(member: zipfile.ZipInfo) -> bool:
    # Symlink metadata is only meaningful on Unix-created archives.
    mode = (member.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _resolve_safe_zip_target(extract_dir_path: str, member_name: str) -> str:
    normalized_name = member_name.replace("\\", "/")
    drive, _ = os.path.splitdrive(normalized_name)
    if drive or normalized_name.startswith("/"):
        raise UnsafeZipArchiveError("ZIP contains an absolute path entry.")

    parts = [part for part in normalized_name.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise UnsafeZipArchiveError("ZIP contains a path traversal entry.")

    target_path = os.path.abspath(os.path.join(extract_dir_path, *parts))
    root_path = os.path.abspath(extract_dir_path)
    try:
        if os.path.commonpath([root_path, target_path]) != root_path:
            raise UnsafeZipArchiveError("ZIP entry escapes extraction directory.")
    except ValueError as exc:
        raise UnsafeZipArchiveError("ZIP entry resolves outside extraction directory.") from exc

    return target_path


def _validate_zip_archive(archive: zipfile.ZipFile):
    members = archive.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise UnsafeZipArchiveError("ZIP contains too many files to extract safely.")

    total_uncompressed_bytes = 0
    for member in members:
        if _is_zip_symlink(member):
            raise UnsafeZipArchiveError("ZIP contains a symbolic link entry.")

        _resolve_safe_zip_target(".", member.filename)

        if member.is_dir():
            continue

        if member.file_size < 0:
            raise UnsafeZipArchiveError("ZIP contains an invalid file size entry.")

        if member.file_size > MAX_SINGLE_ZIP_ENTRY_BYTES:
            raise UnsafeZipArchiveError("ZIP contains a file that is too large to extract safely.")

        total_uncompressed_bytes += member.file_size
        if total_uncompressed_bytes > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise UnsafeZipArchiveError("ZIP exceeds the allowed extraction size.")


def extract_zip_archive(zip_path: str, extract_dir_path: str):
    with zipfile.ZipFile(zip_path, "r") as archive:
        _validate_zip_archive(archive)
        for member in archive.infolist():
            target_path = _resolve_safe_zip_target(extract_dir_path, member.filename)
            if member.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with archive.open(member, "r") as source, open(target_path, "wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)


async def ensure_zip_extracted(zip_path: str, extract_dir_name: str, extract_dir_path: str):
    if os.path.exists(extract_dir_path):
        return

    lock = get_zip_extraction_lock(extract_dir_name)
    async with lock:
        if os.path.exists(extract_dir_path):
            return

        try:
            await asyncio.to_thread(extract_zip_archive, zip_path, extract_dir_path)
        except UnsafeZipArchiveError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
