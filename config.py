import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
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
