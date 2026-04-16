import html
import json
import os
import re
import secrets
import shutil
import time
import uuid
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse
import aiofiles

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
GOOGLE_DRIVE_PUBLIC_FOLDER_VIEW_URL = "https://drive.google.com/embeddedfolderview"
GOOGLE_DRIVE_PUBLIC_DOWNLOAD_URLS = (
    "https://drive.usercontent.google.com/download",
    "https://drive.google.com/uc",
)

GOOGLE_DRIVE_CLIENT_ID = (os.getenv("GOOGLE_DRIVE_CLIENT_ID", "") or "").strip()
GOOGLE_DRIVE_CLIENT_SECRET = (os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "") or "").strip()
GOOGLE_DRIVE_REDIRECT_URI = (
    os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://127.0.0.1:8000/api/google-drive/auth/callback") or ""
).strip()

_oauth_state_store = {}
_drive_library_cache = {}
SUPPORTED_AUDIO_EXTENSIONS = {".m4b", ".mp3", ".m4a", ".mp4", ".zip"}
SUPPORTED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
GOOGLE_DRIVE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PUBLIC_DRIVE_ENTRY_RE = re.compile(
    r'<div class="flip-entry" id="entry-(?P<entry_id>[^"]+)".*?'
    r'<a href="(?P<href>[^"]+)".*?'
    r'<div class="flip-entry-title">(?P<title>.*?)</div>'
    r'</a>.*?<div class="flip-entry-last-modified"><div>(?P<modified>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
PUBLIC_DOWNLOAD_BLOCK_MARKERS = (
    "fortiguard",
    "access blocked",
    "intrusion prevention",
    "web filter",
    "security gateway",
)
MIME_TYPE_BY_EXTENSION = {
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


def _now_ts():
    return int(time.time())


def is_google_drive_configured():
    return bool(GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET and GOOGLE_DRIVE_REDIRECT_URI)


def _get_saved_google_drive():
    return config.get_google_drive_settings()


def _get_saved_auth():
    google_drive = _get_saved_google_drive()
    return google_drive.get("auth", {})


def _build_cache_key(folder_id: str, mode: str) -> str:
    return f"{mode}:{folder_id}"


def is_google_drive_public_link_mode(status: dict | None = None) -> bool:
    status = status or get_google_drive_status()
    return bool((status.get("folder_id") or "").strip() and not status.get("connected"))


def _guess_drive_mime_type(name: str) -> str:
    ext = os.path.splitext(name or "")[1].lower()
    return MIME_TYPE_BY_EXTENSION.get(ext, "application/octet-stream")


def _public_stream_url(file_id: str, resource_key: str = "") -> str:
    if not file_id:
        return ""
    if resource_key:
        return f"/api/google-drive/files/{file_id}/stream?resource_key={resource_key}"
    return f"/api/google-drive/files/{file_id}/stream"


def get_google_drive_status():
    google_drive = _get_saved_google_drive()
    auth = google_drive.get("auth", {})
    expires_at = int(auth.get("expires_at") or 0)
    connected = bool(auth.get("connected") and auth.get("refresh_token"))
    folder_id = google_drive.get("folder_id", "")
    public_link_mode = bool(folder_id and not connected)
    return {
        "configured": is_google_drive_configured(),
        "connected": connected,
        "folder_id": folder_id,
        "account_email": auth.get("account_email", ""),
        "account_name": auth.get("account_name", ""),
        "expires_at": expires_at,
        "expired": bool(expires_at and expires_at <= _now_ts()),
        "public_link_mode": public_link_mode,
    }


def build_google_drive_auth_url():
    if not is_google_drive_configured():
        raise RuntimeError("Google Drive OAuth is not configured.")

    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = {"created_at": _now_ts()}
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
        "state": state,
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
    if not config.sync_playback_profile_with_google_account(auth_payload.get("account_email", "")):
        raise RuntimeError("Failed to persist playback profile settings.")
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
    if not config.sync_playback_profile_with_google_account(auth_updates.get("account_email", "")):
        raise RuntimeError("Failed to persist playback profile settings.")
    return auth_updates


def disconnect_google_drive():
    _drive_library_cache.clear()
    return config.clear_google_drive_auth()


def extract_google_drive_folder_id(value: str):
    raw_value = (value or "").strip()
    if not raw_value:
        return ""

    if GOOGLE_DRIVE_ID_PATTERN.match(raw_value):
        return raw_value

    candidate = raw_value
    if "://" not in candidate and candidate.startswith("drive.google.com/"):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("Enter a valid Google Drive folder ID or shared folder link.")

    if "drive.google.com" not in parsed.netloc.lower():
        raise RuntimeError("Only Google Drive shared folder links are supported here.")

    query = parse_qs(parsed.query)
    query_id = (query.get("id") or query.get("folder_id") or [""])[0].strip()
    if query_id and GOOGLE_DRIVE_ID_PATTERN.match(query_id):
        return query_id

    segments = [segment for segment in parsed.path.split("/") if segment]
    for index, segment in enumerate(segments):
        if segment == "folders" and index + 1 < len(segments):
            folder_id = segments[index + 1].strip()
            if GOOGLE_DRIVE_ID_PATTERN.match(folder_id):
                return folder_id

    raise RuntimeError("Could not extract a Google Drive folder ID from the provided link.")


def save_google_drive_folder_id(folder_id: str):
    clean_folder_id = extract_google_drive_folder_id(folder_id)
    _drive_library_cache.clear()
    if not config.save_google_drive_folder_id(clean_folder_id):
        raise RuntimeError("Failed to persist Google Drive folder ID.")
    return clean_folder_id


def _parse_public_modified_label(value: str) -> float:
    label = " ".join((value or "").replace("\xa0", " ").split())
    if not label:
        return 0.0

    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(label, fmt).timestamp()
        except ValueError:
            pass

    current_year = datetime.now().year
    for fmt in ("%b %d", "%B %d"):
        try:
            parsed = datetime.strptime(label, fmt).replace(year=current_year)
            if parsed.timestamp() > time.time() + 172800:
                parsed = parsed.replace(year=current_year - 1)
            return parsed.timestamp()
        except ValueError:
            pass
    return 0.0


def _parse_google_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return _parse_public_modified_label(value)


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


async def _fetch_public_folder_html(folder_id: str) -> str:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(
            GOOGLE_DRIVE_PUBLIC_FOLDER_VIEW_URL,
            params={"id": folder_id},
        )
        response.raise_for_status()
        return response.text


def _extract_file_id_from_href(href: str) -> str:
    parsed = urlparse(href)
    segments = [segment for segment in parsed.path.split("/") if segment]
    for index, segment in enumerate(segments):
        if segment == "d" and index + 1 < len(segments):
            return segments[index + 1].strip()
    return ""


def _parse_public_drive_folder_entries(html_text: str) -> list[dict]:
    entries = []
    for match in PUBLIC_DRIVE_ENTRY_RE.finditer(html_text or ""):
        href = html.unescape(match.group("href") or "").strip()
        name = html.unescape(match.group("title") or "").strip()
        modified_label = html.unescape(match.group("modified") or "").strip()
        if not href or not name:
            continue

        file_id = _extract_file_id_from_href(href) or (match.group("entry_id") or "").strip()
        if not file_id:
            continue

        parsed_href = urlparse(href)
        resource_key = (parse_qs(parsed_href.query).get("resourcekey") or [""])[0].strip()
        entries.append({
            "id": file_id,
            "name": name,
            "mimeType": _guess_drive_mime_type(name),
            "size": 0,
            "modifiedTime": modified_label,
            "createdTime": "",
            "webViewLink": href,
            "resourceKey": resource_key,
        })
    return entries


async def _list_public_folder_files(folder_id: str) -> list[dict]:
    html_text = await _fetch_public_folder_html(folder_id)
    entries = _parse_public_drive_folder_entries(html_text)
    if entries:
        return entries

    body_lower = (html_text or "").lower()
    if "request access" in body_lower or "you need access" in body_lower or "sign in" in body_lower:
        raise RuntimeError(
            "The Google Drive folder is not publicly readable. Share it as 'Anyone with the link' and try again."
        )
    raise RuntimeError(
        "The Google Drive shared folder could not be read. Make sure it is public and contains visible files."
    )


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
                "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime,createdTime,webViewLink,resourceKey)",
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
                "fields": "id,name,mimeType,size,modifiedTime,createdTime,webViewLink,resourceKey",
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
    ext = os.path.splitext(name)[1].lower()
    metadata_file = None
    cover_file = None
    for candidate in sidecars:
        candidate_name = candidate.get("name", "")
        candidate_ext = os.path.splitext(candidate_name)[1].lower()
        if candidate_ext == ".json" and metadata_file is None:
            metadata_file = candidate
        elif candidate_ext in SUPPORTED_COVER_EXTENSIONS and cover_file is None:
            cover_file = candidate

    size_bytes = int(file_item.get("size") or 0)
    mtime = _parse_google_timestamp(file_item.get("modifiedTime", ""))
    resource_key = file_item.get("resourceKey", "") or ""
    metadata_resource_key = metadata_file.get("resourceKey", "") if metadata_file else ""
    cover_resource_key = cover_file.get("resourceKey", "") if cover_file else ""
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
        "drive_metadata_name": metadata_file.get("name", "") if metadata_file else "",
        "drive_cover_name": cover_file.get("name", "") if cover_file else "",
        "mime_type": file_item.get("mimeType", ""),
        "web_view_link": file_item.get("webViewLink", ""),
        "resource_key": resource_key,
        "drive_metadata_resource_key": metadata_resource_key,
        "drive_cover_resource_key": cover_resource_key,
        "streamable": ext != ".zip",
    }


def _find_cached_drive_item(folder_id: str, file_id: str) -> dict | None:
    if not folder_id or not file_id:
        return None
    for mode in ("oauth", "public"):
        cached = _drive_library_cache.get(_build_cache_key(folder_id, mode))
        if not isinstance(cached, dict):
            continue
        for item in cached.get("files", []):
            if isinstance(item, dict) and item.get("drive_file_id") == file_id:
                return dict(item)
    return None


def _resolve_public_file_name(folder_id: str, file_id: str, file_name: str = "") -> str:
    if file_name:
        return file_name.strip()
    cached = _find_cached_drive_item(folder_id, file_id)
    if cached:
        return (cached.get("name") or "").strip()
    return ""


async def list_google_drive_library_files(folder_id: str = ""):
    return await list_google_drive_library_files_cached(folder_id=folder_id, force_refresh=False)


async def list_google_drive_library_files_cached(folder_id: str = "", force_refresh: bool = False):
    status = get_google_drive_status()
    target_folder_id = (folder_id or status["folder_id"] or "").strip()
    if not target_folder_id:
        raise RuntimeError("Google Drive folder ID is not configured.")

    public_link_mode = is_google_drive_public_link_mode(status)
    mode = "public" if public_link_mode else "oauth"
    cache_key = _build_cache_key(target_folder_id, mode)
    cached = _drive_library_cache.get(cache_key)
    if not force_refresh and isinstance(cached, dict):
        expires_at = float(cached.get("expires_at") or 0)
        if expires_at > time.time():
            return [dict(item) for item in cached.get("files", [])]

    if public_link_mode:
        raw_files = await _list_public_folder_files(target_folder_id)
    else:
        if not status["configured"]:
            raise RuntimeError("Google Drive OAuth is not configured.")
        if not status["connected"]:
            raise RuntimeError("Google Drive is not connected.")
        raw_files = await _list_raw_folder_files(target_folder_id)

    audio_files, sidecars = _split_drive_files(raw_files)
    library_items = [
        _build_drive_library_item(file_item, sidecars.get(os.path.splitext(file_item.get("name", ""))[0], []))
        for file_item in audio_files
    ]
    library_items.sort(key=lambda item: item.get("mtime", 0), reverse=True)
    _drive_library_cache[cache_key] = {
        "expires_at": time.time() + GOOGLE_DRIVE_LIBRARY_CACHE_TTL_SECONDS,
        "files": [dict(item) for item in library_items],
    }
    return library_items


async def _download_drive_file_to_path(client: httpx.AsyncClient, file_id: str, destination_path: str):
    async with client.stream(
        "GET",
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
    ) as response:
        response.raise_for_status()
        async with aiofiles.open(destination_path, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                await f.write(chunk)
    return destination_path


def _looks_like_public_download_response(response: httpx.Response) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    if response.status_code not in {200, 206}:
        return False
    return not content_type.startswith("text/html")


async def _describe_public_drive_download_failure(response: httpx.Response) -> str:
    final_host = (response.request.url.host or "").lower()
    body_lower = ""
    try:
        body_lower = (await response.aread()).decode("utf-8", errors="ignore").lower()
    except Exception:
        body_lower = ""

    if any(marker in body_lower for marker in PUBLIC_DOWNLOAD_BLOCK_MARKERS):
        return (
            "Your network or security gateway is blocking Google Drive media delivery "
            f"from {final_host or 'drive.usercontent.google.com'}. "
            "Allow drive.usercontent.google.com or try again from a network without this block."
        )
    if "request access" in body_lower or "you need access" in body_lower or response.status_code in {403, 404}:
        return "This Google Drive file is not publicly accessible from the shared folder."
    if "google drive - virus scan warning" in body_lower or "can't scan this file for viruses" in body_lower:
        return "Google Drive did not expose a direct public download for this file."
    return (
        "Google Drive public download failed"
        f" with status {response.status_code} from {final_host or 'drive.usercontent.google.com'}."
    )


async def _request_public_drive_file(
    client: httpx.AsyncClient,
    file_id: str,
    resource_key: str = "",
    range_header: str = "",
    stream: bool = False,
) -> httpx.Response:
    headers = {}
    if range_header:
        headers["Range"] = range_header

    last_error = None
    for download_url in GOOGLE_DRIVE_PUBLIC_DOWNLOAD_URLS:
        params = {"id": file_id, "export": "download", "confirm": "t"}
        if resource_key:
            params["resourcekey"] = resource_key
        request = client.build_request("GET", download_url, params=params, headers=headers)
        response = await client.send(request, stream=stream)
        if _looks_like_public_download_response(response):
            return response

        detail = await _describe_public_drive_download_failure(response)
        await response.aclose()
        last_error = RuntimeError(detail)

    raise last_error or RuntimeError("Google Drive public download failed.")


async def _open_public_drive_file(
    file_id: str,
    resource_key: str = "",
    range_header: str = "",
    stream: bool = False,
):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        response = await _request_public_drive_file(
            client,
            file_id,
            resource_key=resource_key,
            range_header=range_header,
            stream=stream,
        )
        return client, response
    except Exception:
        await client.aclose()
        raise


def _extract_size_from_headers(headers: httpx.Headers) -> int:
    content_range = headers.get("content-range", "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)
    content_length = headers.get("content-length", "")
    if content_length.isdigit():
        return int(content_length)
    return 0


async def _probe_public_drive_file_size(file_id: str, resource_key: str = "") -> int:
    client, response = await _open_public_drive_file(
        file_id,
        resource_key=resource_key,
        range_header="bytes=0-0",
        stream=False,
    )
    try:
        return _extract_size_from_headers(response.headers)
    finally:
        await response.aclose()
        await client.aclose()


async def _read_public_drive_json(file_id: str, resource_key: str = "") -> dict:
    client, response = await _open_public_drive_file(file_id, resource_key=resource_key, stream=False)
    try:
        payload = json.loads(response.content.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    finally:
        await response.aclose()
        await client.aclose()


async def _download_public_drive_file_to_path(file_id: str, destination_path: str, resource_key: str = "") -> str:
    client, response = await _open_public_drive_file(file_id, resource_key=resource_key, stream=True)
    try:
        async with aiofiles.open(destination_path, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                await f.write(chunk)
        return destination_path
    finally:
        await response.aclose()
        await client.aclose()


async def build_google_drive_metadata(
    file_id: str,
    metadata_file_id: str = "",
    cover_file_id: str = "",
    file_name: str = "",
    resource_key: str = "",
    metadata_resource_key: str = "",
    cover_resource_key: str = "",
):
    status = get_google_drive_status()
    public_link_mode = is_google_drive_public_link_mode(status)
    target_folder_id = (status.get("folder_id") or "").strip()

    if public_link_mode:
        resolved_file_name = _resolve_public_file_name(target_folder_id, file_id, file_name=file_name) or file_name or file_id
        size_bytes = await _probe_public_drive_file_size(file_id, resource_key=resource_key)
        file_info = {
            "name": resolved_file_name,
            "size": size_bytes,
            "resourceKey": resource_key,
        }
    else:
        file_info = await _get_drive_file_metadata(file_id)
        if resource_key and not file_info.get("resourceKey"):
            file_info["resourceKey"] = resource_key

    file_name = file_info.get("name", "")
    base_name, ext = os.path.splitext(file_name)
    ext = ext.lower()
    size_bytes = int(file_info.get("size") or 0)

    metadata = {
        "title": base_name or file_name,
        "book_id": bookmark_service.build_book_id(file_name, size_bytes=size_bytes),
        "mode": "zip" if ext == ".zip" else "single",
        "file_name": file_name,
        "chapters": [],
        "cover_url": _public_stream_url(cover_file_id, cover_resource_key) if cover_file_id else None,
        "local_cover": None,
        "source": "google_drive",
        "drive_file_id": file_id,
        "stream_url": _public_stream_url(file_id, resource_key),
    }

    if metadata_file_id:
        if public_link_mode:
            sidecar_data = await _read_public_drive_json(metadata_file_id, resource_key=metadata_resource_key)
        else:
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
        metadata["cover_url"] = _public_stream_url(cover_file_id, cover_resource_key)

    metadata.setdefault("title", base_name or file_name)
    metadata["book_id"] = bookmark_service.build_book_id(file_name, size_bytes=size_bytes, metadata=metadata)
    metadata["file_name"] = file_name
    metadata["source"] = "google_drive"
    metadata["drive_file_id"] = file_id
    metadata["stream_url"] = _public_stream_url(file_id, resource_key)
    metadata["local_cover"] = None
    return metadata


async def open_google_drive_stream(file_id: str, range_header: str = "", resource_key: str = ""):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    status = get_google_drive_status()
    if is_google_drive_public_link_mode(status):
        client, response = await _open_public_drive_file(
            file_id,
            resource_key=resource_key,
            range_header=range_header,
            stream=True,
        )
    else:
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


async def probe_google_drive_stream(file_id: str, resource_key: str = ""):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    status = get_google_drive_status()
    if is_google_drive_public_link_mode(status):
        client, response = await _open_public_drive_file(
            file_id,
            resource_key=resource_key,
            range_header="bytes=0-0",
            stream=False,
        )
    else:
        client = await _get_authorized_client()
        response = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media", "supportsAllDrives": "true"},
            headers={"Range": "bytes=0-0"},
        )
        response.raise_for_status()

    try:
        return {
            "status": "ok",
            "content_type": response.headers.get("content-type", ""),
            "size_bytes": _extract_size_from_headers(response.headers),
        }
    finally:
        await response.aclose()
        await client.aclose()


async def import_google_drive_file(
    file_id: str,
    metadata_file_id: str = "",
    cover_file_id: str = "",
    file_name: str = "",
    metadata_file_name: str = "",
    cover_file_name: str = "",
    resource_key: str = "",
    metadata_resource_key: str = "",
    cover_resource_key: str = "",
):
    if not file_id:
        raise RuntimeError("Missing Google Drive file ID.")

    status = get_google_drive_status()
    public_link_mode = is_google_drive_public_link_mode(status)
    target_folder_id = (status.get("folder_id") or "").strip()

    if public_link_mode:
        resolved_file_name = _resolve_public_file_name(target_folder_id, file_id, file_name=file_name)
        if not resolved_file_name:
            raise RuntimeError("Google Drive file name is not available for import.")
    else:
        file_info = await _get_drive_file_metadata(file_id)
        resolved_file_name = file_info.get("name", "").strip()
        if not resolved_file_name:
            raise RuntimeError("Google Drive file metadata did not include a file name.")

    base_name = os.path.splitext(resolved_file_name)[0]
    task_id = f"gdrive-import-{uuid.uuid4()}"
    work_dir = processor.prepare_task_work_dir(task_id)
    staged_paths = []
    try:
        if public_link_mode:
            staged_main_path = os.path.join(work_dir, resolved_file_name)
            await _download_public_drive_file_to_path(file_id, staged_main_path, resource_key=resource_key)
            staged_paths.append(staged_main_path)

            if metadata_file_id:
                resolved_metadata_name = metadata_file_name or f"{base_name}.json"
                staged_metadata_path = os.path.join(work_dir, resolved_metadata_name)
                await _download_public_drive_file_to_path(
                    metadata_file_id,
                    staged_metadata_path,
                    resource_key=metadata_resource_key,
                )
                staged_paths.append(staged_metadata_path)

            if cover_file_id:
                resolved_cover_name = cover_file_name or f"{base_name}.jpg"
                staged_cover_path = os.path.join(work_dir, resolved_cover_name)
                await _download_public_drive_file_to_path(
                    cover_file_id,
                    staged_cover_path,
                    resource_key=cover_resource_key,
                )
                staged_paths.append(staged_cover_path)
        else:
            async with await _get_authorized_client() as client:
                staged_main_path = os.path.join(work_dir, resolved_file_name)
                await _download_drive_file_to_path(client, file_id, staged_main_path)
                staged_paths.append(staged_main_path)

                if metadata_file_id:
                    metadata_info = await _get_drive_file_metadata(metadata_file_id)
                    resolved_metadata_name = metadata_info.get("name", metadata_file_name or f"{base_name}.json")
                    staged_metadata_path = os.path.join(work_dir, resolved_metadata_name)
                    await _download_drive_file_to_path(client, metadata_file_id, staged_metadata_path)
                    staged_paths.append(staged_metadata_path)

                if cover_file_id:
                    cover_info = await _get_drive_file_metadata(cover_file_id)
                    resolved_cover_name = cover_info.get("name", cover_file_name or f"{base_name}.jpg")
                    staged_cover_path = os.path.join(work_dir, resolved_cover_name)
                    await _download_drive_file_to_path(client, cover_file_id, staged_cover_path)
                    staged_paths.append(staged_cover_path)

        moved_main = processor.move_to_library(staged_paths[0], resolved_file_name)
        if not moved_main:
            raise RuntimeError("Failed to move imported audiobook into the local library.")

        imported = {
            "file_name": resolved_file_name,
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
