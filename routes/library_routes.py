import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api_models import ImportedBookIdsResponse, LibraryFilesResponse, PlaybackMetadataResponse
import bookmark_service
import config
import library_service
import zip_service
from route_helpers import resolve_download_path


router = APIRouter()


@router.get("/api/library", response_model=LibraryFilesResponse)
async def get_library():
    return {"files": library_service.list_library_files(config.DOWNLOADS_DIR)}


@router.get("/api/library/imported-book-ids", response_model=ImportedBookIdsResponse)
async def get_imported_book_ids():
    return {"book_ids": library_service.list_library_book_ids(config.DOWNLOADS_DIR)}


@router.get("/api/files/{file_name:path}")
async def download_file(file_name: str):
    file_path = resolve_download_path(file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/api/metadata/{file_name}", response_model=PlaybackMetadataResponse)
async def get_metadata(file_name: str):
    file_path = resolve_download_path(file_name)
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    if file_name.endswith(".zip"):
        payload = await zip_service.build_zip_metadata(file_path, file_name, config.DOWNLOADS_DIR)
        if isinstance(payload, dict):
            payload["book_id"] = bookmark_service.build_book_id(
                file_name, size_bytes=os.path.getsize(file_path), metadata=payload
            )
        return payload

    json_path = os.path.join(os.path.dirname(file_path), f"{base_name}.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                payload["book_id"] = bookmark_service.build_book_id(
                    file_name, size_bytes=os.path.getsize(file_path), metadata=payload
                )
                return payload
        except Exception:
            raise HTTPException(status_code=500, detail="Metadata read failed")

    raise HTTPException(status_code=404, detail="Metadata not found")
