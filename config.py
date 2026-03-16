import os
import sys
import json

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

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
    DOWNLOADS_DIR = path
    try:
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings["downloads_dir"] = path
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
        if not os.path.exists(path):
            os.makedirs(path)
        return True
    except Exception as e:
        return False

DEBUG_LOG = os.path.join(BASE_DIR, "app_debug.log")

# FFmpeg configuration
# Default paths for your system, can be overridden by env variables
FFMPEG_PATH = os.getenv("FFMPEG_PATH", r"C:\Users\pavel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.WinGet.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", r"C:\Users\pavel\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.WinGet.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffprobe.exe")

# Retention settings
FILE_EXPIRE_SECONDS = 3600  # Delete files after 1 hour
STORE_EXPIRE_SECONDS = 7200 # Clear progress info after 2 hours

# Ensure downloads directory exists
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)
