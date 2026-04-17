import asyncio
import time
import os
import json
import shutil
from backfill_covers import process_file
import config

config.DOWNLOADS_DIR = "test_downloads"

async def event_loop_lag_monitor(lags, stop_event):
    while not stop_event.is_set():
        start = time.perf_counter()
        await asyncio.sleep(0.001)
        lag = time.perf_counter() - start - 0.001
        if lag > 0.001:
            lags.append(lag)

async def setup():
    if os.path.exists("test_downloads"):
        shutil.rmtree("test_downloads")
    os.makedirs("test_downloads", exist_ok=True)

    # Create 500 large files to simulate heavier I/O
    large_data = {"title": "Test Book", "author": "Test Author", "data": "X" * 100000}
    for i in range(500):
        large_data["local_cover"] = f"book_{i}.jpg"
        with open(f"test_downloads/book_{i}.json", "w") as f:
            json.dump(large_data, f)
        with open(f"test_downloads/book_{i}.jpg", "w") as f:
            f.write("fake image")

async def run_benchmark():
    await setup()
    lags = []
    stop_event = asyncio.Event()

    # Run the lag monitor and the tasks concurrently
    monitor_task = asyncio.create_task(event_loop_lag_monitor(lags, stop_event))

    tasks = [process_file(f"book_{i}.m4b", {}) for i in range(500)]

    start_time = time.perf_counter()
    await asyncio.gather(*tasks)
    end_time = time.perf_counter()

    stop_event.set()
    await monitor_task

    print(f"Time taken: {end_time - start_time:.4f} seconds")
    print(f"Total significant lags (>1ms): {len(lags)}")
    print(f"Max lag: {max(lags) if lags else 0:.4f} seconds")
    if lags:
        print(f"Average lag: {sum(lags)/len(lags):.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
