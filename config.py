import copy
import json
import logging
import os
import shutil
import uuid


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
            "token_type": "",
            "scope": "",
            "expires_at": 0,
            "account_email": "",
            "account_name": "",
        }
    }
}


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
            merged[key] = value
    return merged


def load_settings():
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
    return copy.deepcopy(settings.get("google_drive", DEFAULT_SETTINGS["google_drive"]))


def save_google_drive_settings(google_drive_settings):
    settings = load_settings()
    settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive_settings or {})
    return save_settings(settings)


def clear_google_drive_auth():
    settings = load_settings()
    google_drive = settings.get("google_drive", {})
    google_drive["auth"] = copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"])
    settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
    return save_settings(settings)


def update_google_drive_auth(auth_updates):
    settings = load_settings()
    google_drive = settings.get("google_drive", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]))
    auth = google_drive.get("auth", copy.deepcopy(DEFAULT_SETTINGS["google_drive"]["auth"]))
    auth.update(auth_updates or {})
    google_drive["auth"] = _deep_merge(DEFAULT_SETTINGS["google_drive"]["auth"], auth)
    settings["google_drive"] = _deep_merge(DEFAULT_SETTINGS["google_drive"], google_drive)
    return save_settings(settings)


def save_google_drive_folder_id(folder_id):
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
