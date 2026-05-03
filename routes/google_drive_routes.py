import html
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

import google_drive_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/google-drive", tags=["google-drive"])


class GoogleDriveFolderRequest(BaseModel):
    folder_id: str = ""


class GoogleDriveImportRequest(BaseModel):
    file_id: str
    metadata_file_id: str = ""
    cover_file_id: str = ""
    file_name: str = ""
    metadata_file_name: str = ""
    cover_file_name: str = ""
    resource_key: str = ""
    metadata_resource_key: str = ""
    cover_resource_key: str = ""


@router.get("/status")
async def google_drive_status():
    return google_drive_service.get_google_drive_status()


@router.get("/auth/url")
async def google_drive_auth_url():
    try:
        return google_drive_service.build_google_drive_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/auth/callback", response_class=HTMLResponse)
async def google_drive_auth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        message = html.escape(error_description or error)
        return HTMLResponse(
            f"<html><body><h2>Google Drive connection failed</h2><p>{message}</p></body></html>",
            status_code=400,
        )

    try:
        auth = await google_drive_service.exchange_code_for_google_tokens(code, state)
    except (RuntimeError, httpx.HTTPError, ValueError) as exc:
        logger.exception("Google Drive OAuth callback failed")
        message = html.escape(str(exc))
        return HTMLResponse(
            f"<html><body><h2>Google Drive connection failed</h2><p>{message}</p></body></html>",
            status_code=400,
        )

    account_name = html.escape(auth.get("account_name") or auth.get("account_email") or "Google account")
    return HTMLResponse(
        "<html><body>"
        "<h2>Google Drive connected</h2>"
        f"<p>Connected as {account_name}.</p>"
        "<p>You can close this window and return to SonicBook.</p>"
        "</body></html>"
    )


@router.post("/disconnect")
async def google_drive_disconnect():
    if not google_drive_service.disconnect_google_drive():
        raise HTTPException(status_code=500, detail="Failed to clear Google Drive auth settings")
    return {"status": "success"}


@router.post("/folder")
async def google_drive_save_folder(request: GoogleDriveFolderRequest):
    try:
        folder_id = google_drive_service.save_google_drive_folder_id(request.folder_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "folder_id": folder_id}


@router.get("/library")
async def google_drive_library(folder_id: str = "", refresh: bool = False):
    try:
        files = await google_drive_service.list_google_drive_library_files_cached(folder_id, force_refresh=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"files": files}


@router.post("/import")
async def google_drive_import(request: GoogleDriveImportRequest):
    try:
        result = await google_drive_service.import_google_drive_file(
            request.file_id,
            request.metadata_file_id,
            request.cover_file_id,
            request.file_name,
            request.metadata_file_name,
            request.cover_file_name,
            request.resource_key,
            request.metadata_resource_key,
            request.cover_resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", **result}


@router.get("/metadata/{file_id}")
async def google_drive_metadata(
    file_id: str,
    metadata_file_id: str = "",
    cover_file_id: str = "",
    file_name: str = "",
    resource_key: str = "",
    metadata_resource_key: str = "",
    cover_resource_key: str = "",
):
    try:
        return await google_drive_service.build_google_drive_metadata(
            file_id,
            metadata_file_id,
            cover_file_id,
            file_name,
            resource_key,
            metadata_resource_key,
            cover_resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files/{file_id}/probe")
async def google_drive_probe_file(file_id: str, resource_key: str = ""):
    try:
        return await google_drive_service.probe_google_drive_stream(file_id, resource_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("Google Drive stream probe failed")
        raise HTTPException(status_code=502, detail="Google Drive file probe failed") from exc


@router.get("/files/{file_id}/stream")
async def google_drive_stream_file(file_id: str, request: Request, resource_key: str = ""):
    try:
        client, response, headers = await google_drive_service.open_google_drive_stream(
            file_id,
            request.headers.get("range", ""),
            resource_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def stream_generator():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_generator(),
        status_code=response.status_code,
        headers=headers,
        media_type=response.headers.get("content-type"),
    )
