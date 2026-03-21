import asyncio
import os

from fastapi import APIRouter

from api_models import FolderResponse, FolderSelectionResponse
import config


router = APIRouter()


@router.get("/api/settings/folder", response_model=FolderResponse)
async def get_folder():
    return {"folder": config.DOWNLOADS_DIR}


@router.post("/api/settings/choose_folder", response_model=FolderSelectionResponse)
async def choose_folder():
    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(initialdir=config.DOWNLOADS_DIR, title="Select Download Folder")
        root.destroy()
        return folder

    loop = asyncio.get_running_loop()
    selected = await loop.run_in_executor(None, open_dialog)

    if selected:
        selected = os.path.abspath(selected)
        if config.save_downloads_dir(selected):
            return {"status": "success", "folder": selected}

    return {"status": "cancelled", "folder": config.DOWNLOADS_DIR}
