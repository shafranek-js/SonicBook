import time
import os
import shutil
import library_service
import config

TEST_DIR = "test_downloads"

def setup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)
    for i in range(5000):
        with open(os.path.join(TEST_DIR, f"book_{i}.mp3"), "w") as f:
            f.write("a")
        if i % 2 == 0:
            with open(os.path.join(TEST_DIR, f"book_{i}.json"), "w") as f:
                f.write(f'{{"title": "book", "file_name": "book_{i}.mp3"}}')

def list_library_book_ids_optimized(downloads_dir: str) -> list[str]:
    # Try to return book_ids by just looking at the cached items rather than doing a full rescan
    # But wait, the issue states "N+1 Disk Read in Loop".
    # Looking at `list_library_book_ids`:
    # for item in _scan_library(downloads_dir):
    #     name = item.get("name", "")
    pass

def benchmark_original():
    start = time.perf_counter()
    library_service.list_library_book_ids(TEST_DIR)
    return time.perf_counter() - start

def main():
    setup()

    # Warmup
    library_service._scan_library(TEST_DIR)

    t0 = time.perf_counter()
    for _ in range(5):
        library_service.list_library_book_ids(TEST_DIR)
    t1 = time.perf_counter()
    print(f"Original: {(t1-t0)/5:.4f}s")

    shutil.rmtree(TEST_DIR)

if __name__ == "__main__":
    main()
