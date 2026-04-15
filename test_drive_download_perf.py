import asyncio
import time
import os
import aiofiles
import random

class MockResponse:
    def __init__(self, content):
        self.content = content
    def raise_for_status(self):
        pass

class MockClient:
    # 1GB
    CONTENT = b"0" * (1 * 1024 * 1024 * 1024)
    async def get(self, url, params=None):
        return MockResponse(self.CONTENT)

async def _download_drive_file_to_path_sync(client, file_id, destination_path):
    response = await client.get(f"https://www.googleapis.com/drive/v3/files/{file_id}")
    with open(destination_path, "wb") as f:
        f.write(response.content)
    return destination_path

async def _download_drive_file_to_path_async(client, file_id, destination_path):
    response = await client.get(f"https://www.googleapis.com/drive/v3/files/{file_id}")
    async with aiofiles.open(destination_path, "wb") as f:
        await f.write(response.content)
    return destination_path

async def background_task(interval, result_list):
    """A task that runs continuously to measure loop blocking."""
    while True:
        start = time.perf_counter()
        await asyncio.sleep(interval)
        duration = time.perf_counter() - start
        if duration > interval + 0.05: # Allow 50ms of jitter before counting it as a block
            result_list.append(duration - interval)

async def measure(func, name):
    client = MockClient()
    dest = f"test_{name}_{random.randint(1000, 9999)}.dat"
    block_times = []

    # Ensure file exists so write isn't cached as easily
    bg_task = asyncio.create_task(background_task(0.01, block_times))

    start_time = time.perf_counter()
    # Execute the function in an async block
    task = asyncio.create_task(func(client, "dummy_id", dest))
    await task
    end_time = time.perf_counter()

    bg_task.cancel()

    if os.path.exists(dest):
        os.remove(dest)

    total_time = end_time - start_time
    max_block = max(block_times) if block_times else 0
    total_block = sum(block_times)

    print(f"[{name}]")
    print(f"  Total Time: {total_time:.4f} s")
    print(f"  Max Event Loop Block: {max_block:.4f} s")
    print(f"  Total Event Loop Block: {total_block:.4f} s")
    print()

async def main():
    print("Running Baseline (Sync Write)...")
    await measure(_download_drive_file_to_path_sync, "sync")

    print("Running Optimized (Async Write)...")
    await measure(_download_drive_file_to_path_async, "async")

if __name__ == "__main__":
    asyncio.run(main())
