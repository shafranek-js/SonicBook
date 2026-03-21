from fastapi import APIRouter, HTTPException

from api_models import (
    BookmarkResponse,
    BookmarkUpdateRequest,
    BookmarksResponse,
    SaveBookmarkResponse,
    StatusResponse,
)
import bookmark_service


router = APIRouter()


@router.get("/api/bookmarks", response_model=BookmarksResponse)
async def get_bookmarks():
    return {"bookmarks": bookmark_service.list_bookmarks()}


@router.get("/api/bookmarks/{book_id:path}", response_model=BookmarkResponse)
async def get_bookmark(book_id: str):
    return {"bookmark": bookmark_service.get_bookmark(book_id)}


@router.post("/api/bookmarks/{book_id:path}", response_model=SaveBookmarkResponse)
async def save_bookmark(book_id: str, request: BookmarkUpdateRequest):
    try:
        bookmark = bookmark_service.save_bookmark(book_id, request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "bookmark": bookmark}


@router.delete("/api/bookmarks/{book_id:path}", response_model=StatusResponse)
async def delete_bookmark(book_id: str):
    if not bookmark_service.delete_bookmark(book_id):
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")
    return {"status": "success"}
