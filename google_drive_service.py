import os
import secrets
import shutil
import time
import uuid
import json
from datetime import datetime
from urllib.parse import urlencode

import httpx

import bookmark_service
import config
import processor


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_OIDC_SCOPES = "openid email profile"
GOOGLE_DEFAULT_SCOPES = f"{GOOGLE_DRIVE_SCOPE} {GOOGLE_OIDC_SCOPES}"
GOOGLE_DRIVE_LIBRARY_CACHE_TTL_SECONDS = 45

GOOGLE_DRIVE_CLIENT_ID = (os.getenv("GOOGLE_DRIVE_CLIENT_ID", "") or "").strip()
GOOGLE_DRIVE_CLIENT_SECRET = (os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "") or "").strip()
GOOGLE_DRIVE_REDIRECT_URI = (
    os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://127.0.0.1:8000/api/google-drive/auth/callback") or ""
).strip()

_oauth_state_store = {}
_drive_library_cache = {}
SUPPORTED_AUDIO_EXTENSIONS = {".m4b", ".mp3", ".m4a", ".mp4", ".zip"}
SUPPORTED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _now_ts():
    return int(time.time())


def is_google_drive_configured():
    return bool(GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET and GOOGLE_DRIVE_REDIRECT_URI)


def _get_saved_google_drive():
    return config.get_google_drive_settings()


def _get_saved_auth():
    google_drive = _get_saved_google_drive()
    return google_drive.get("auth", {})


def get_google_drive_status():
    google_drive = _get_saved_google_drive()
    auth = google_drive.get("auth", {})
    expires_at = int(auth.get("expires_at") or 0)
    connected = bool(auth.get("connected") and auth.get("refresh_token"))
    return {
        "configured": is_google_drive_configured(),
        "connected": connected,
        "folder_id": google_drive.get("folder_id", ""),
        "account_email": auth.get("account_email", ""),
        "account_name": auth.get("account_name", ""),
        "expires_at": expires_at,
        "expired": bool(expires_at and expires_at <= _now_ts()),
    }


def build_google_drive_auth_url():
    if not is_google_drive_configured():
        raise RuntimeError("Google Drive OAuth is not configured.")

    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = {
        "created_at": _now_ts()
    }
    query = urlencode({
        "client_id": GOOGLE_DRIVE_CLIENT_ID,
        "redirect_uri": GOOGLE_DRIVE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_DEFAULT_SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    })
    return {
        "auth_url": f"{GOOGLE_AUTH_URL}?{query}",
        "state": state
    }


def _pop_valid_state(state):
    if not state:
        return None
    payload = _oauth_state_store.pop(state, None)
    if not payload:
        return None
    if _now_ts() - int(payload.get("created_at", 0)) > 900:
        return None
    return payload


async def exchange_code_for_google_tokens(code: str, state: str):
    if not is_google_drive_configured():
        raise RuntimeError("Google Drive OAuth is not configured.")
    if not code:
        raise RuntimeError("Missing OAuth code.")
    if _pop_valid_state(state) is None:
        raise RuntimeError("Invalid or expired OAuth state.")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_DRIVE_CLIENT_ID,
                "client_secret": GOOGLE_DRIVE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_DRIVE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        access_token = token_data.get("access_token", "")
        if not access_token:
            raise RuntimeError("Google OAuth response did not include an access token.")

        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_response.raise_for_status()
        user = userinfo_response.json()

    expires_in = int(token_data.get("expires_in") or 0)
    auth_payload = {
        "connected": True,
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token", _get_saved_auth().get("refresh_token", "")),
        "token_type": token_data.get("token_type", ""),
        "scope": token_data.get("scope", GOOGLE_DEFAULT_SCOPES),
        "expires_at": _now_ts() + expires_in if expires_in else 0,
        "account_email": user.get("email", ""),
        "account_name": user.get("name", ""),
    }
    if not config.update_google_drive_auth(auth_payload):
        raise RuntimeError("Failed to persist Google Drive auth settings.")
    return auth_payload


async def refresh_google_drive_access_token(force: bool = False):
    if not is_google_drive_configured():
        raise RuntimeError("Google Drive OAuth is not configured.")

    auth = _get_saved_auth()
    refresh_token = (auth.get("refresh_token") or "").strip()
    if not refresh_token:
        raise RuntimeError("No Google Drive refresh token is available.")

    expires_at = int(auth.get("expires_at") or 0)
    if not force and expires_at and expires_at - _now_ts() > 120:
        return auth

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_DRIVE_CLIENT_ID,
                "client_secret": GOOGLE_DRIVE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        token_data = token_response.json()

    expires_in = int(token_data.get("expires_in") or 0)
    auth_updates = {
        "connected": True,
        "access_token": token_data.get("access_token", auth.get("access_token", "")),
        "token_type": token_data.get("token_type", auth.get("token_type", "")),
        "scope": token_data.get("scope", auth.get("scope", GOOGLE_DEFAULT_SCOPES)),
        "expires_at": _now_ts() + expires_in if expires_in else auth.get("expires_at", 0),
        "refresh_token": refresh_token,
        "account_email": auth.get("account_email", ""),
        "account_name": auth.get("account_name", ""),
    }
    if not config.update_google_drive_auth(auth_updates):
        raise RuntimeError("Failed to persist refreshed Google Drive token.")
    return auth_updates


def disconnect_google_drive():
    _drive_library_cache.clear()
    return config.clear_google_drive_auth()


def save_google_drive_folder_id(folder_id: str):
    clean_folder_id = (folder_id or "").strip()
    if clean_folder_id and "/" in clean_folder_id:
        raise RuntimeError("Folder ID must be a Google Drive folder identifier, not a URL.")
    _drive_library_cache.clear()
    if not config.save_google_drive_folder_id(clean_folder_id):
        raise RuntimeError("Failed to persist Google Drive folder ID.")
    return clean_folder_id


def _parse_google_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


async def _get_authorized_client():
    auth = await refresh_google_drive_access_token()
    access_token = auth.get("access_token", "")
    if not access_token:
        raise RuntimeError("Google Drive access token is not available.")
    client = httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return client


async def _list_raw_folder_files(folder_id: str):
    files = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    async with await _get_authorized_client() as client:
        while True:
            response = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "q": query,
                    "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime,createdTime,webViewLink)",
                    "pageSize": 1000,
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                    "pageToken": page_token,
                },
            )
            response.raise_for_status()
            payload = response.json()
            files.extend(payload.get("files", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    return files


async def _get_drive_file_metadata(file_id: str):
    async with await _get_authorized_client() as client:
        response = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={
                "fields": "id,name,mimeType,size,modifiedTime,createdTime,webViewLink",
                "supportsAllDrives": "true",
            },
        )
        response.raise_for_status()
        return response.json()


def _split_drive_files(raw_files: list[dict]):
    audio_files = []
    sidecars = {}
    for file_item in raw_files:
        name = file_item.get("name", "")
        root, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext in SUPPORTED_AUDIO_EXTENSIONS:
            audio_files.append(file_item)
            continue
        if ext not in {".json", *SUPPORTED_COVER_EXTENSIONS}:
            continue
        sidecars.setdefault(root, []).append(file_item)
    return audio_files, sidecars


def _build_drive_library_item(file_item: dict, sidecars: list[dict]):
    name = file_item.get("name", "")
    root, ext = os.path.splitext(name)
    ext = ext.lower()
    metadata_file = None
    cover_file = None
    for candidate in sidecars:
        candidate_name = candidate.get("name", "")
        _, ext = os.path.splitext(candidate_name)
        ext = ext.lower()
        if ext == ".json" and metadata_file is None:
            metadata_file = candidate
        elif ext in SUPPORTED_COVER_EXTENSIONS and cover_file is None:
            cover_file = candidate

    size_bytes = int(file_item.get("size") or 0)
    mtime = _parse_google_timestamp(file_item.get("modifiedTime", ""))
    return {
        "source": "google_drive",
        "name": name,
        "book_id": bookmark_service.build_book_id(name, size_bytes=size_bytes),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else 0,
        "has_meta": metadata_file is not None,
        "duration_seconds": None,
        "chapter_count": None,
        "mtime": mtime,
        "drive_file_id": file_item.get("id", ""),
        "drive_metadata_file_id": metadata_file.get("id", "") if metadata_file else "",
        "drive_cover_file_id": cover_file.get("id", "") if cover_file else "",
        "mime_type": file_item.get("mimeType", ""),
        "web_view_link": file_item.get("webViewLink", ""),
        "streamable": ext != ".zip",
    }


async def list_google_drive_library_files(folder_id: str = ""):
    return await list_google_drive_library_files_cached(folder_id=folder_id, force_refresh=False)


async def list_google_drive_library_files_cached(folder_id: str = "", force_refresh: bool = False):
    status = get_google_drive_status()
    if not status["configured"]:
        raise RuntimeError("Google Drive OAuth is not configured.")
    if not status["connected"]:
        raise RuntimeError("Google Drive is not connected.")

    target_folder_id = (folder_id or status["folder_id"] or "").strip()
    if not target_folder_id:
        raise RuntimeError("Google Drive folder ID is not configured.")

    cached = _drive_library_cache.get(target_folder_id)
    if not force_refresh and isinstance(cached, dict):
        expires_at = float(cached.get("expires_at") or 0)
        if expires_at > time.time():
            return [dict(item) for item in cached.get("files", [])]

    raw_files = await _list_raw_folder_files(target_folder_id)
    audio_files, sidecars = _split_drive_files(raw_files)
    library_items = [
        _build_drive_library_item(file_item, sidecars.get(os.path.splitext(file_item.get("name", ""))[0], []))
        for file_item in audio_files
    ]
    library_items.sort(key=lambda item: item.get("mtime", 0), reverse=True)
    _drive_library_cache[target_folder_id] = {
        "expires_at": time.time() + GOOGLE_DRIVE_LIBRARY_CACHE_TTL_SECONDS,
        "files": [dict(item) for item in library_items],
    }
    return library_items


async def _download_drive_file_to_path(client: httpx.AsyncClient, file_id: str, destination_path: str):
    response = await client.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
    )
    response.raise_for_status()
    with open(destination_path, "wb") as f:
        f.write(response.content)
    return destination_path


async def build_google_drive_metadata(file_id: str, metadata_file_id: str = "", cover_file_id: str = ""):
    file_info = await _get_drive_file_metadata(file_id)
    file_name = file_info.get("name", "")
    base_name, ext = os.path.splitext(file_name)
    ext = ext.lower()

    metadata = {
        "title": base_name or file_name,
        "book_id": bookmark_service.build_book_id(file_name, size_bytes=int(file_info.get("size") or 0)),
        "mode": "zip" if ext == ".zip" else "single",
        "file_name": file_name,
        "chapters": [],
        "cover_url": f"/api/google-drive/files/{cover_file_id}/stream" if cover_file_id else None,
        "local_cover": None,
        "source": "google_drive",
        "drive_file_id": file_id,
        "stream_url": f"/api/google-drive/files/{file_id}/stream",
    }

    if metadata_file_id:
        async with await _get_authorized_client() as client:
            response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{metadata_file_id}",
                params={"alt": "media", "supportsAllDrives": "true"},
            )
            response.raise_for_status()
            sidecar_data = json.loads(response.content.decode("utf-8"))
            if isinstance(sidecar_data, dict):
                metadata.update(sidecar_data)

    if cover_file_id:
        metadata["cover_url"] = f"/api/google-drive/files/{cover_file_id}/stream"

    metadata.setdefault("title", base_name or file_name)
    metadata["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=int(file_info.get("size") or 0), metadata=metadata)
    metadata["file_name"] = file_name
    metadata["source"] = "google_drive"
    metadata["drive_file_id"] = file_id
    metadata["stream_url"] = f"/api/google-drive/files/{file_id}/stream"
    metadata["local_cover"] = None
    return metadata


async def open_google_drive_stream(file_id: str, range_header: str = ""):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    client = await _get_authorized_client()
    headers = {}
    if range_header:
        headers["Range"] = range_header

    request = client.build_request(
        "GET",
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
        headers=headers,
    )
    response = await client.send(request, stream=True)
    try:
        response.raise_for_status()
    except Exception:
        await response.aclose()
        await client.aclose()
        raise

    passthrough_headers = {}
    for header_name in ("content-type", "content-length", "content-range", "accept-ranges", "cache-control", "etag", "last-modified"):
        value = response.headers.get(header_name)
        if value:
            passthrough_headers[header_name] = value
    return client, response, passthrough_headers


async def import_google_drive_file(file_id: str, metadata_file_id: str = "", cover_file_id: str = ""):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    file_info = await _get_drive_file_metadata(file_id)
    file_name = file_info.get("name", "").strip()
    if not file_name:
        raise RuntimeError("Google Drive file metadata did not include a file name.")

    task_id = f"gdrive-import-{uuid.uuid4()}"
    work_dir = processor.prepare_task_work_dir(task_id)
    staged_paths = []
    try:
        async with await _get_authorized_client() as client:
            staged_main_path = os.path.join(work_dir, file_name)
            await _download_drive_file_to_path(client, file_id, staged_main_path)
            staged_paths.append(staged_main_path)

            if metadata_file_id:
                metadata_info = await _get_drive_file_metadata(metadata_file_id)
                metadata_name = metadata_info.get("name", f"{os.path.splitext(file_name)[0]}.json")
                staged_metadata_path = os.path.join(work_dir, metadata_name)
                await _download_drive_file_to_path(client, metadata_file_id, staged_metadata_path)
                staged_paths.append(staged_metadata_path)

            if cover_file_id:
                cover_info = await _get_drive_file_metadata(cover_file_id)
                cover_name = cover_info.get("name", f"{os.path.splitext(file_name)[0]}.jpg")
                staged_cover_path = os.path.join(work_dir, cover_name)
                await _download_drive_file_to_path(client, cover_file_id, staged_cover_path)
                staged_paths.append(staged_cover_path)

        moved_main = processor.move_to_library(staged_main_path, file_name)
        if not moved_main:
            raise RuntimeError("Failed to move imported audiobook into the local library.")

        imported = {
            "file_name": file_name,
            "metadata_name": "",
            "cover_name": "",
        }
        for staged_path in staged_paths[1:]:
            dest_name = os.path.basename(staged_path)
            moved_path = processor.move_to_library(staged_path, dest_name)
            if moved_path:
                if dest_name.lower().endswith(".json"):
                    imported["metadata_name"] = dest_name
                else:
                    imported["cover_name"] = dest_name

        return imported
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
