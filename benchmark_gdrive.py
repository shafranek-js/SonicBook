import asyncio
import time
import os
from unittest.mock import AsyncMock, MagicMock
import sys

# Mocking modules that are not available
mock_httpx = MagicMock()
sys.modules["httpx"] = mock_httpx

# Mocking aiofiles
mock_aiofiles = MagicMock()
mock_file_context = MagicMock()
mock_file = AsyncMock()
mock_file_context.__aenter__.return_value = mock_file
mock_aiofiles.open.return_value = mock_file_context
sys.modules["aiofiles"] = mock_aiofiles

mock_PIL = MagicMock()
sys.modules["PIL"] = mock_PIL

import google_drive_service

async def mock_aiter_bytes():
    chunk = b"0" * 1024 * 1024  # 1MB chunk
    for _ in range(50):  # 50MB total
        yield chunk
        # Simulate some network delay
        await asyncio.sleep(0.01)

async def benchmark():
    print("Starting benchmark...")

    # Mocking _open_public_drive_file
    mock_response = MagicMock()
    mock_response.aiter_bytes = mock_aiter_bytes
    mock_response.aclose = AsyncMock()

    mock_client = MagicMock()
    mock_client.aclose = AsyncMock()

    original_open = google_drive_service._open_public_drive_file
    google_drive_service._open_public_drive_file = AsyncMock(return_value=(mock_client, mock_response))

    dest = "test_download.bin"

    counter = 0
    stop_event = asyncio.Event()

    async def background_task():
        nonlocal counter
        while not stop_event.is_set():
            counter += 1
            await asyncio.sleep(0) # Yield control

    bg_task = asyncio.create_task(background_task())

    start_time = time.time()
    await google_drive_service._download_public_drive_file_to_path("dummy_id", dest)
    end_time = time.time()

    stop_event.set()
    await bg_task

    print(f"Download took: {end_time - start_time:.4f} seconds")
    print(f"Background task increments: {counter}")

    # Restore
    google_drive_service._open_public_drive_file = original_open

if __name__ == "__main__":
    asyncio.run(benchmark())
