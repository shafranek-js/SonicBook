import asyncio
import json
import logging
import mimetypes
import os
from urllib.parse import quote

import aiofiles
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

import bookmark_service
import config
import library_service
import zip_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])
STREAM_CHUNK_SIZE = 1024 * 1024

MEDIA_TYPE_OVERRIDES = {
    ".m4b": "audio/mp4",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".zip": "application/zip",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".json": "application/json",
}


def guess_media_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in MEDIA_TYPE_OVERRIDES:
        return MEDIA_TYPE_OVERRIDES[ext]
    guessed_type, _ = mimetypes.guess_type(file_path)
    return guessed_type or "application/octet-stream"


def build_inline_content_disposition(file_path: str) -> str:
    return f"inline; filename*=utf-8''{quote(os.path.basename(file_path))}"


def parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None

    units, _, raw_range = range_header.partition("=")
    if units.strip().lower() != "bytes" or not raw_range:
        raise HTTPException(status_code=416, detail="Invalid range unit")

    first_range = raw_range.split(",", 1)[0].strip()
    start_str, sep, end_str = first_range.partition("-")
    if not sep:
        raise HTTPException(status_code=416, detail="Invalid range format")

    try:
        if start_str:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        else:
            suffix_length = int(end_str)
            if suffix_length <= 0:
                raise HTTPException(status_code=416, detail="Invalid range suffix")
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid byte range") from exc

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    end = min(end, file_size - 1)
    return start, end


async def iter_file_range(file_path: str, start: int, end: int):
    async with aiofiles.open(file_path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = await f.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def resolve_download_path(file_name: str) -> str:
    if not file_name:
        raise HTTPException(status_code=400, detail="Invalid file path")

    normalized_name = os.path.normpath(file_name)
    drive, _ = os.path.splitdrive(normalized_name)
    if drive or os.path.isabs(file_name) or os.path.isabs(normalized_name):
        raise HTTPException(status_code=400, detail="Invalid file path")

    downloads_root = os.path.abspath(config.DOWNLOADS_DIR)
    candidate_path = os.path.abspath(os.path.join(downloads_root, normalized_name))
    try:
        if os.path.commonpath([downloads_root, candidate_path]) != downloads_root:
            raise HTTPException(status_code=400, detail="Invalid file path")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid file path") from exc

    return candidate_path


@router.get("/api/library")
async def get_library():
    return {"files": library_service.list_library_files(config.DOWNLOADS_DIR)}


@router.get("/api/library/imported-book-ids")
async def get_imported_book_ids():
    return {"book_ids": library_service.list_library_book_ids(config.DOWNLOADS_DIR)}


@router.delete("/api/library/files/{file_name:path}")
async def delete_library_file(file_name: str):
    file_path = resolve_download_path(file_name)
    if not await asyncio.to_thread(os.path.exists, file_path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        return await asyncio.to_thread(library_service.delete_library_book, file_name, config.DOWNLOADS_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to delete library file: %s", file_name)
        raise HTTPException(status_code=500, detail="Failed to delete file") from exc


@router.get("/api/files/{file_name:path}")
async def download_file(file_name: str, request: Request):
    file_path = resolve_download_path(file_name)
    if await asyncio.to_thread(os.path.exists, file_path):
        media_type = guess_media_type(file_path)
        common_headers = {
            "accept-ranges": "bytes",
            "content-disposition": build_inline_content_disposition(file_path),
        }
        file_size = await asyncio.to_thread(os.path.getsize, file_path)
        range_header = request.headers.get("range", "")
        byte_range = parse_range_header(range_header, file_size) if range_header else None
        if byte_range is not None:
            start, end = byte_range
            headers = {
                **common_headers,
                "content-length": str(end - start + 1),
                "content-range": f"bytes {start}-{end}/{file_size}",
            }
            return StreamingResponse(
                iter_file_range(file_path, start, end),
                status_code=206,
                media_type=media_type,
                headers=headers,
            )

        response = FileResponse(
            path=file_path,
            media_type=media_type,
            filename=os.path.basename(file_path),
            content_disposition_type="inline",
        )
        response.headers["accept-ranges"] = "bytes"
        response.headers["content-disposition"] = common_headers["content-disposition"]
        return response
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/api/metadata/{file_name}")
async def get_metadata(file_name: str):
    file_path = resolve_download_path(file_name)
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    if file_name.endswith(".zip"):
        payload = await zip_service.build_zip_metadata(file_path, file_name, config.DOWNLOADS_DIR)
        if isinstance(payload, dict):
            size_bytes = await asyncio.to_thread(os.path.getsize, file_path)
            payload["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=size_bytes, metadata=payload)
        return payload

    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if await asyncio.to_thread(os.path.exists, json_path):
        try:
            async with aiofiles.open(json_path, "r", encoding="utf-8") as f:
                content = await f.read()
                payload = json.loads(content)
            if isinstance(payload, dict):
                size_bytes = await asyncio.to_thread(os.path.getsize, file_path)
                payload["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=size_bytes, metadata=payload)
                return payload
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.exception("Failed to read metadata sidecar: %s", json_path)
            raise HTTPException(status_code=500, detail="Metadata read failed") from exc
    raise HTTPException(status_code=404, detail="Metadata not found")
