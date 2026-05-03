import copy
import json
import logging
import os
import shutil
import uuid
import importlib
import threading
from contextlib import contextmanager


logger = logging.getLogger(__name__)


# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
WORK_DIR = os.path.join(BASE_DIR, ".sonicbook-work")
DEBUG_LOG = os.path.join(BASE_DIR, "app_debug.log")

DEFAULT_DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
DEFAULT_SETTINGS = {
    "downloads_dir": DEFAULT_DOWNLOADS_DIR,
    "instance_id": "",
    "playback_profile": {
        "id": "",
        "source": "auto",
    },
    "google_drive": {
        "folder_id": "",
        "auth": {
            "connected": False,
            "access_token": "",
            "refresh_token": "",
            "tokens_in_keyring": False,
            "token_type": "",
            "scope": "",
            "expires_at": 0,
            "account_email": "",
            "account_name": "",
        }
    }
}
GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE = "SonicBook.GoogleDriveAuth"
_json_file_locks: dict[str, threading.RLock] = {}
_json_file_locks_guard = threading.Lock()


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
        logger.warning("Failed to load .env", exc_info=True)


load_dotenv_file()


def _deep_merge(defaults, override):
    if not isinstance(defaults, dict):
        return copy.deepcopy(override)

    merged = copy.deepcopy(defaults)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _get_json_file_lock(path: str) -> threading.RLock:
    normalized_path = os.path.abspath(path or "")
    with _json_file_locks_guard:
        lock = _json_file_locks.get(normalized_path)
        if lock is None:
            lock = threading.RLock()
            _json_file_locks[normalized_path] = lock
        return lock


@contextmanager
def locked_json_file(path: str):
    lock = _get_json_file_lock(path)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _get_keyring_module():
    try:
        return importlib.import_module("keyring")
    except Exception:
        return None


def _get_google_drive_keyring_user(settings: dict) -> str:
    instance_id, _ = _ensure_instance_id_in_settings(settings)
    return f"{instance_id}:google_drive_auth"


def _load_google_drive_tokens_from_keyring(settings: dict) -> dict:
    keyring = _get_keyring_module()
    if keyring is None:
        return {}

    user = _get_google_drive_keyring_user(settings)
    try:
        raw = keyring.get_password(GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE, user)
    except Exception:
        logger.warning("Failed to read Google Drive tokens from keyring", exc_info=True)
        return {}
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except Exception:
        logger.warning("Invalid Google Drive token payload in keyring", exc_info=True)
        return {}

    if not isinstance(payload, dict):
        return {}

    return {
        "access_token": str(payload.get("access_token") or ""),
        "refresh_token": str(payload.get("refresh_token") or ""),
    }


def _save_google_drive_tokens_to_keyring(settings: dict, access_token: str, refresh_token: str) -> bool:
    keyring = _get_keyring_module()
    if keyring is None:
        return False

    user = _get_google_drive_keyring_user(settings)
    payload = json.dumps(
        {
            "access_token": str(access_token or ""),
            "refresh_token": str(refresh_token or ""),
        },
        ensure_ascii=False,
    )
    try:
        keyring.set_password(GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE, user, payload)
    except Exception:
        logger.warning("Failed to persist Google Drive tokens in keyring", exc_info=True)
        return False
    return True


def _clear_google_drive_tokens_from_keyring(settings: dict):
    keyring = _get_keyring_module()
    if keyring is None:
        return

    user = _get_google_drive_keyring_user(settings)
    try:
        keyring.delete_password(GOOGLE_DRIVE_TOKEN_KEYRING_SERVICE, user)
    except Exception:
        # It's fine when no entry exists or backend cannot delete.
        pass


def load_settings():
    with locked_json_file(SETTINGS_FILE):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        settings = _deep_merge(DEFAULT_SETTINGS, loaded)
        except Exception:
            logger.exception("Failed to load settings")
        return settings


def _normalize_playback_profile_id(value: str) -> str:
    normalized = " ".join(str(value or "").strip().split()).lower()
    return normalized[:160]


def _ensure_instance_id_in_settings(settings: dict) -> tuple[str, bool]:
    instance_id = str(settings.get("instance_id") or "").strip().lower()
    if instance_id:
        return instance_id, False
    instance_id = uuid.uuid4().hex
    settings["instance_id"] = instance_id
    return instance_id, True


def save_settings(settings):
    with locked_json_file(SETTINGS_FILE):
        temp_settings_file = SETTINGS_FILE + ".tmp"
        try:
            settings_to_save = _deep_merge(DEFAULT_SETTINGS, settings or {})
            _ensure_instance_id_in_settings(settings_to_save)
            with open(temp_settings_file, "w", encoding="utf-8") as f:
                json.dump(settings_to_save, f, ensure_ascii=False, indent=2)
            os.replace(temp_settings_file, SETTINGS_FILE)
            return True
        except Exception:
            logger.exception("Failed to save settings")
            if os.path.exists(temp_settings_file):
                try:
                    os.remove(temp_settings_file)
                except OSError:
                    pass
            return False


def get_google_drive_settings():
    settings = load_settings()
    google_drive = copy.deepcopy(settings.get("google_drive", DEFAULT_SETTINGS["google_drive"]))
    auth = copy.deepcopy(google_drive.get("auth", DEFAULT_SETTINGS["google_drive"]["auth"]))

    if auth.get("tokens_in_keyring"):
        secure_tokens = _load_google_drive_tokens_from_keyring(settings)
        if secure_tokens.get("access_token") or secure_tokens.get("refresh_token"):
            auth["access_token"] = secure_tokens.get("access_token", "")
            auth["refresh_token"] = secure_tokens.get("refresh_token", "")

    google_drive["auth"] = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], auth)
    return google_drive


def clear_google_drive_auth():
    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        _clear_google_drive_tokens_from_keyring(settings)
        google_drive = settings.get("google_drive", {})
        google_drive["auth"] = copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"])
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return save_settings(settings)


def update_google_drive_auth(auth_updates):
    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        google_drive = settings.get("google_drive", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]))
        auth = copy.deepcopy(google_drive.get("auth", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"])))

        if auth.get("tokens_in_keyring"):
            secure_tokens = _load_google_drive_tokens_from_keyring(settings)
            if secure_tokens:
                auth.update(secure_tokens)

        auth.update(auth_updates or {})

        access_token = str(auth.get("access_token") or "")
        refresh_token = str(auth.get("refresh_token") or "")
        if access_token or refresh_token:
            if _save_google_drive_tokens_to_keyring(settings, access_token, refresh_token):
                auth["access_token"] = ""
                auth["refresh_token"] = ""
                auth["tokens_in_keyring"] = True
            else:
                auth["tokens_in_keyring"] = False
        else:
            _clear_google_drive_tokens_from_keyring(settings)
            auth["tokens_in_keyring"] = False

        google_drive["auth"] = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], auth)
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return save_settings(settings)


def save_google_drive_folder_id(folder_id):
    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        google_drive = settings.get("google_drive", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]))
        google_drive["folder_id"] = (folder_id or "").strip()
        settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
        return save_settings(settings)


def load_downloads_dir():
    settings = load_settings()
    path = settings.get("downloads_dir")
    if path and os.path.exists(path):
        return path
    return DEFAULT_DOWNLOADS_DIR


def get_instance_id() -> str:
    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        instance_id, changed = _ensure_instance_id_in_settings(settings)
        if changed:
            save_settings(settings)
        return instance_id


def get_playback_profile_status() -> dict:
    settings = load_settings()
    playback_profile = settings.get("playback_profile", {})
    configured_id = _normalize_playback_profile_id(playback_profile.get("id", ""))
    configured_source = str(playback_profile.get("source") or "auto").strip().lower()
    account_email = _normalize_playback_profile_id(
        settings.get("google_drive", {}).get("auth", {}).get("account_email", "")
    )

    if not configured_id and account_email:
        playback_profile["id"] = account_email
        playback_profile["source"] = "google_account"
        settings["playback_profile"] = _deep_merge(DEFAULT_SETTINGS["playback_profile"], playback_profile)
        save_settings(settings)
        configured_id = account_email
        configured_source = "google_account"

    if configured_id:
        resolved_id = configured_id
        source = "google_account" if configured_source == "google_account" else "manual"
    elif account_email:
        resolved_id = account_email
        source = "google_account"
    else:
        resolved_id = f"device:{get_instance_id()}"
        source = "device"

    return {
        "configured_id": configured_id,
        "profile_id": resolved_id,
        "source": source,
        "account_email": account_email,
    }


def save_playback_profile_id(profile_id: str) -> dict:
    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        playback_profile = settings.get("playback_profile", copy.deepcopy(DEFAULT_SETTINGS["playback_profile"]))
        normalized = _normalize_playback_profile_id(profile_id)
        playback_profile["id"] = normalized
        playback_profile["source"] = "manual" if normalized else "auto"
        settings["playback_profile"] = _deep_merge(DEFAULT_SETTINGS["playback_profile"], playback_profile)
        if not save_settings(settings):
            raise RuntimeError("Failed to persist playback profile.")
        return get_playback_profile_status()


def sync_playback_profile_with_google_account(account_email: str) -> bool:
    normalized_email = _normalize_playback_profile_id(account_email)
    if not normalized_email:
        return True

    with locked_json_file(SETTINGS_FILE):
        settings = load_settings()
        playback_profile = settings.get("playback_profile", copy.deepcopy(DEFAULT_SETTINGS["playback_profile"]))
        current_id = _normalize_playback_profile_id(playback_profile.get("id", ""))
        current_source = str(playback_profile.get("source") or "auto").strip().lower()

        if current_id and current_source == "manual":
            return True
        if current_id == normalized_email and current_source == "google_account":
            return True

        playback_profile["id"] = normalized_email
        playback_profile["source"] = "google_account"
        settings["playback_profile"] = _deep_merge(DEFAULT_SETTINGS["playback_profile"], playback_profile)
        return save_settings(settings)


DOWNLOADS_DIR = load_downloads_dir()


def save_downloads_dir(path):
    global DOWNLOADS_DIR
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        with locked_json_file(SETTINGS_FILE):
            settings = load_settings()
            settings["downloads_dir"] = path
            if save_settings(settings):
                DOWNLOADS_DIR = path
                return True
            return False
    except Exception:
        logger.exception("Failed to save downloads directory")
        return False


# FFmpeg configuration
# Defaults rely on PATH, but can be overridden by env variables.
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
YTDLP_CONCURRENCY = int(os.getenv("YTDLP_CONCURRENCY", "16"))
MULTI_CONNECTION_DOWNLOADS = os.getenv("MULTI_CONNECTION_DOWNLOADS", "1").strip().lower() not in {"0", "false", "no", "off"}
MULTI_CONNECTION_MIN_BYTES = max(1, int(os.getenv("MULTI_CONNECTION_MIN_BYTES", str(64 * 1024 * 1024))))
MULTI_CONNECTION_MAX_SEGMENTS = max(1, min(8, int(os.getenv("MULTI_CONNECTION_MAX_SEGMENTS", "4"))))


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
