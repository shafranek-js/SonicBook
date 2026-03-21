import os
from urllib.parse import urlparse

from fastapi import HTTPException

import config


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
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")

    return candidate_path


def validate_book_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid book URL")
    return candidate


def build_user_error_message(exc: Exception, fallback: str) -> str:
    message = str(exc).strip()
    if not message:
        return fallback
    return message
