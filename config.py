import os
import sys
import json
import shutil

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
WORK_DIR = os.path.join(BASE_DIR, ".sonicbook-work")

def load_downloads_dir():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                path = settings.get("downloads_dir")
                if path and os.path.exists(path):
                    return path
    except:
        pass
    return os.path.join(BASE_DIR, "downloads")

DOWNLOADS_DIR = load_downloads_dir()

def save_downloads_dir(path):
    global DOWNLOADS_DIR
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings["downloads_dir"] = path
        temp_settings_file = SETTINGS_FILE + ".tmp"
        with open(temp_settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
        os.replace(temp_settings_file, SETTINGS_FILE)
        DOWNLOADS_DIR = path
        return True
    except Exception as e:
        temp_settings_file = SETTINGS_FILE + ".tmp"
        if os.path.exists(temp_settings_file):
            try:
                os.remove(temp_settings_file)
            except OSError:
                pass
        return False

DEBUG_LOG = os.path.join(BASE_DIR, "app_debug.log")

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
STORE_EXPIRE_SECONDS = 7200 # Clear progress info after 2 hours

# Ensure downloads directory exists
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Ensure local staging/work directory exists
if not os.path.exists(WORK_DIR):
    os.makedirs(WORK_DIR)
