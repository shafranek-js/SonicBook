import asyncio
import time
import os
import aiofiles

class MockResponse:
    def __init__(self, size_mb, chunk_size=1024*1024): # 1MB chunks
        self.total_bytes = size_mb * 1024 * 1024
        self.chunk_size = chunk_size
        self.chunk = b"a" * self.chunk_size
        self.emitted = 0

    async def aiter_bytes(self):
        while self.emitted < self.total_bytes:
            # yield to event loop
            await asyncio.sleep(0.001)
            yield self.chunk
            self.emitted += self.chunk_size

async def mock_download_sync(size_mb, path):
    response = MockResponse(size_mb)
    with open(path, "wb") as f:
        async for chunk in response.aiter_bytes():
            # simulate some heavy synchronous writing that blocks
            time.sleep(0.01) # fake delay for disk write block
            f.write(chunk)

async def mock_download_async(size_mb, path):
    response = MockResponse(size_mb)
    async with aiofiles.open(path, "wb") as f:
        async for chunk in response.aiter_bytes():
            await asyncio.sleep(0.01) # fake delay for async disk write
            await f.write(chunk)

async def background_task(interval, counters):
    try:
        while True:
            await asyncio.sleep(interval)
            counters[0] += 1
    except asyncio.CancelledError:
        pass

async def test_performance(func, name, path):
    counters = [0]
    task = asyncio.create_task(background_task(0.01, counters))
    start_time = time.perf_counter()
    await func(100, path) # 100MB
    duration = time.perf_counter() - start_time
    task.cancel()

    print(f"[{name}] Duration: {duration:.2f}s, Background ticks: {counters[0]}")
    if os.path.exists(path):
        os.remove(path)

async def main():
    print("Testing sync file write...")
    await test_performance(mock_download_sync, "Sync", "sync.bin")
    print("\nTesting async file write...")
    await test_performance(mock_download_async, "Async", "async.bin")

if __name__ == "__main__":
    asyncio.run(main())
