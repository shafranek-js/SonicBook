import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import bookmark_service
import config

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PlaybackProfileRequest(BaseModel):
    profile_id: str = ""


@router.get("/folder")
async def get_folder():
    return {"folder": config.DOWNLOADS_DIR}


@router.get("/playback-profile")
async def get_playback_profile():
    return {
        **config.get_playback_profile_status(),
        **bookmark_service.get_state_storage_status(),
    }


@router.post("/playback-profile")
async def save_playback_profile(request: PlaybackProfileRequest):
    try:
        config.save_playback_profile_id(request.profile_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "success",
        **config.get_playback_profile_status(),
        **bookmark_service.get_state_storage_status(),
    }


@router.post("/choose_folder")
async def choose_folder():
    import sys

    script = """
import sys
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.wm_attributes('-topmost', 1)
folder = filedialog.askdirectory(initialdir=sys.argv[1], title="Select Download Folder")
root.destroy()
if folder:
    sys.stdout.write(folder)
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        config.DOWNLOADS_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    selected = stdout.decode("utf-8", errors="replace").strip()

    if selected:
        selected = os.path.abspath(selected)
        if config.save_downloads_dir(selected):
            return {"status": "success", "folder": selected}

    return {"status": "cancelled", "folder": config.DOWNLOADS_DIR}
