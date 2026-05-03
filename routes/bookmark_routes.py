from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import bookmark_service

router = APIRouter(tags=["bookmarks"])


class BookmarkUpdateRequest(BaseModel):
    time: float = 0.0
    duration: float = 0.0
    track: int = 0
    file_name: str = ""
    source: str = ""
    completed: bool | None = None


class ActivePlaybackStateRequest(BaseModel):
    book_id: str = ""
    file_name: str = ""
    source: str = ""
    drive_file_id: str = ""
    drive_metadata_file_id: str = ""
    drive_cover_file_id: str = ""
    drive_resource_key: str = ""
    drive_metadata_resource_key: str = ""
    drive_cover_resource_key: str = ""
    size_bytes: int = 0


@router.get("/api/bookmarks")
async def get_bookmarks():
    return {
        "bookmarks": bookmark_service.list_bookmarks(),
        "last_active": bookmark_service.get_last_active(),
    }


@router.get("/api/bookmarks/{book_id:path}")
async def get_bookmark(book_id: str):
    return {"bookmark": bookmark_service.get_bookmark(book_id)}


@router.post("/api/bookmarks/{book_id:path}")
async def save_bookmark(book_id: str, request: BookmarkUpdateRequest):
    try:
        bookmark = bookmark_service.save_bookmark(book_id, request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "bookmark": bookmark}


@router.delete("/api/bookmarks/{book_id:path}")
async def delete_bookmark(book_id: str):
    if not bookmark_service.delete_bookmark(book_id):
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")
    return {"status": "success"}


@router.post("/api/playback/active")
async def save_active_playback(request: ActivePlaybackStateRequest):
    try:
        playback_state = bookmark_service.save_last_active(request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "last_active": playback_state}
