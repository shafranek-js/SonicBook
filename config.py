import base64
import copy
import ctypes
import json
import os
import shutil
from ctypes import wintypes

from json_storage import locked_json_path, read_json_unlocked, write_json_unlocked

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
GOOGLE_DRIVE_AUTH_FILE = os.path.join(BASE_DIR, ".google_drive_auth.json")
WORK_DIR = os.path.join(BASE_DIR, ".sonicbook-work")
DEBUG_LOG = os.path.join(BASE_DIR, "app_debug.log")

DEFAULT_DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
DEFAULT_SETTINGS = {
    "downloads_dir": DEFAULT_DOWNLOADS_DIR,
    "google_drive": {
        "folder_id": "",
        "auth": {
            "connected": False,
            "access_token": "",
            "refresh_token": "",
            "token_type": "",
            "scope": "",
            "expires_at": 0,
            "account_email": "",
            "account_name": "",
        }
    }
}


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _create_data_blob(data: bytes):
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer


def _dpapi_encrypt(data: bytes) -> bytes:
    if os.name != "nt":
        return data

    in_blob, in_buffer = _create_data_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(  # type: ignore[attr-defined]
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError(ctypes.get_last_error())

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)  # type: ignore[attr-defined]


def _dpapi_decrypt(data: bytes) -> bytes:
    if os.name != "nt":
        return data

    in_blob, in_buffer = _create_data_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(  # type: ignore[attr-defined]
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError(ctypes.get_last_error())

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)  # type: ignore[attr-defined]


def load_dotenv_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


load_dotenv_file()


def _deep_merge(defaults, override):
    if not isinstance(defaults, dict):
        return copy.deepcopy(override)

    merged = copy.deepcopy(defaults)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings():
    with locked_json_path(SETTINGS_FILE):
        return _load_settings_unlocked()


def _load_settings_unlocked():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    try:
        loaded = read_json_unlocked(SETTINGS_FILE, default={})
        if isinstance(loaded, dict):
            settings = _deep_merge(DEFAULT_SETTINGS, loaded)
    except Exception:
        pass
    return settings


def save_settings(settings):
    with locked_json_path(SETTINGS_FILE):
        return _save_settings_unlocked(settings)


def _save_settings_unlocked(settings):
    try:
        write_json_unlocked(SETTINGS_FILE, settings)
        return True
    except Exception:
        temp_settings_file = SETTINGS_FILE + ".tmp"
        if os.path.exists(temp_settings_file):
            try:
                os.remove(temp_settings_file)
            except OSError:
                pass
        return False


def _default_google_drive_auth():
    return copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"])


def _sanitize_google_drive_auth_for_settings(auth):
    safe_auth = _default_google_drive_auth()
    safe_auth.update(auth or {})
    safe_auth["access_token"] = ""
    safe_auth["refresh_token"] = ""
    safe_auth["connected"] = bool((auth or {}).get("refresh_token"))
    return safe_auth


def _load_google_drive_auth_secret():
    with locked_json_path(GOOGLE_DRIVE_AUTH_FILE):
        if not os.path.exists(GOOGLE_DRIVE_AUTH_FILE):
            return _default_google_drive_auth()
        try:
            payload = read_json_unlocked(GOOGLE_DRIVE_AUTH_FILE, default={})
            ciphertext = base64.b64decode(payload.get("ciphertext", "") or "")
            if not ciphertext:
                return _default_google_drive_auth()
            plaintext = _dpapi_decrypt(ciphertext)
            auth = json.loads(plaintext.decode("utf-8"))
            if not isinstance(auth, dict):
                return _default_google_drive_auth()
            return _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], auth)
        except Exception:
            return _default_google_drive_auth()


def _save_google_drive_auth_secret(auth):
    normalized_auth = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], auth or {})
    ciphertext = _dpapi_encrypt(json.dumps(normalized_auth, ensure_ascii=False).encode("utf-8"))
    payload = {
        "version": 1,
        "backend": "dpapi" if os.name == "nt" else "plaintext",
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    temp_file = GOOGLE_DRIVE_AUTH_FILE + ".tmp"
    with locked_json_path(GOOGLE_DRIVE_AUTH_FILE):
        try:
            write_json_unlocked(GOOGLE_DRIVE_AUTH_FILE, payload)
            return True
        except Exception:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            return False


def _clear_google_drive_auth_secret():
    with locked_json_path(GOOGLE_DRIVE_AUTH_FILE):
        try:
            if os.path.exists(GOOGLE_DRIVE_AUTH_FILE):
                os.remove(GOOGLE_DRIVE_AUTH_FILE)
            return True
        except OSError:
            return False


def _migrate_legacy_google_drive_auth():
    with locked_json_path(SETTINGS_FILE):
        settings = _load_settings_unlocked()
        google_drive = settings.get("google_drive", {})
        stored_auth = google_drive.get("auth", {})
        if not isinstance(stored_auth, dict):
            return

        if not stored_auth.get("access_token") and not stored_auth.get("refresh_token"):
            return

        if not _save_google_drive_auth_secret(stored_auth):
            return

        google_drive["auth"] = _sanitize_google_drive_auth_for_settings(stored_auth)
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        _save_settings_unlocked(settings)


def get_google_drive_settings():
    _migrate_legacy_google_drive_auth()
    settings = load_settings()
    google_drive = copy.deepcopy(settings.get("google_drive", DEFAULT_SETTINGS["google_drive"]))
    safe_auth = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], google_drive.get("auth", {}))
    secure_auth = _load_google_drive_auth_secret()
    google_drive["auth"] = _deep_merge(safe_auth, secure_auth)
    if not google_drive["auth"].get("refresh_token"):
        google_drive["auth"]["connected"] = False
    return google_drive


def save_google_drive_settings(google_drive_settings):
    _migrate_legacy_google_drive_auth()
    with locked_json_path(SETTINGS_FILE):
        settings = _load_settings_unlocked()
        merged_google_drive = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive_settings or {})
        auth = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], merged_google_drive.get("auth", {}))
        if auth.get("access_token") or auth.get("refresh_token"):
            if not _save_google_drive_auth_secret(auth):
                return False
        merged_google_drive["auth"] = _sanitize_google_drive_auth_for_settings(auth)
        settings["google_drive"] = merged_google_drive
        return _save_settings_unlocked(settings)


def clear_google_drive_auth():
    _migrate_legacy_google_drive_auth()
    with locked_json_path(SETTINGS_FILE):
        settings = _load_settings_unlocked()
        google_drive = settings.get("google_drive", {})
        google_drive["auth"] = copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"])
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return _clear_google_drive_auth_secret() and _save_settings_unlocked(settings)


def update_google_drive_auth(auth_updates):
    _migrate_legacy_google_drive_auth()
    with locked_json_path(SETTINGS_FILE):
        settings = _load_settings_unlocked()
        google_drive = settings.get("google_drive", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]))
        auth = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], google_drive.get("auth", {}))
        auth = _deep_merge(auth, _load_google_drive_auth_secret())
        auth.update(auth_updates or {})
        if not _save_google_drive_auth_secret(auth):
            return False
        google_drive["auth"] = _sanitize_google_drive_auth_for_settings(auth)
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return _save_settings_unlocked(settings)


def save_google_drive_folder_id(folder_id):
    with locked_json_path(SETTINGS_FILE):
        settings = _load_settings_unlocked()
        google_drive = settings.get("google_drive", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]))
        google_drive["folder_id"] = (folder_id or "").strip()
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return _save_settings_unlocked(settings)


def load_downloads_dir():
    settings = load_settings()
    path = settings.get("downloads_dir")
    if path and os.path.exists(path):
        return path
    return DEFAULT_DOWNLOADS_DIR


DOWNLOADS_DIR = load_downloads_dir()


def save_downloads_dir(path):
    global DOWNLOADS_DIR
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        with locked_json_path(SETTINGS_FILE):
            settings = _load_settings_unlocked()
            settings["downloads_dir"] = path
            if _save_settings_unlocked(settings):
                DOWNLOADS_DIR = path
                return True
            return False
    except Exception:
        return False


# FFmpeg configuration
# Defaults rely on PATH, but can be overridden by env variables.
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")


def ensure_binary_available(binary_name, configured_value, env_var_name):
    if shutil.which(configured_value):
        return

    if os.path.isfile(configured_value):
        return

    raise RuntimeError(
        f"{binary_name} not found: '{configured_value}'. "
        f"Add it to PATH or set {env_var_name}."
    )


def ensure_ffmpeg_binaries():
    ensure_binary_available("ffmpeg", FFMPEG_PATH, "FFMPEG_PATH")
    ensure_binary_available("ffprobe", FFPROBE_PATH, "FFPROBE_PATH")


# Retention settings
FILE_EXPIRE_SECONDS = 3600  # Delete files after 1 hour
STORE_EXPIRE_SECONDS = 7200  # Clear progress info after 2 hours


def ensure_runtime_directories():
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)


ensure_runtime_directories()
