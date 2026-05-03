import os
import string
from urllib.parse import urlparse


def sanitize_filename(name):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    cleaned = "".join(c for c in name if c in valid_chars and c != ",")
    return " ".join(cleaned.split()).strip(". ")[:100]


def resolve_cover_extension(cover_url, content_type):
    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"

    url_ext = os.path.splitext(urlparse(cover_url).path)[1].lower()
    if url_ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if url_ext == ".jpeg" else url_ext

    return ".jpg"
