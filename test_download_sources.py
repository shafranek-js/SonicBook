import unittest
from unittest.mock import AsyncMock, patch
import os
import tempfile

import config
import download_sources


class FakeStreamResponse:
    def __init__(self, status_code=206, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def aiter_bytes(self, chunk_size=1024 * 256):
        for chunk in self._chunks:
            yield chunk

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    responses = []
    requested_ranges = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def stream(self, method, url, headers=None, timeout=None):
        self.requested_ranges.append((headers or {}).get("Range", ""))
        if not self.responses:
            raise AssertionError("No fake stream response queued")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class TestSingleFileDownloadSelection(unittest.IsolatedAsyncioTestCase):
    async def test_uses_multi_connection_when_probe_is_large_enough(self):
        progress = AsyncMock()
        with patch.object(config, "MULTI_CONNECTION_DOWNLOADS", True), \
             patch.object(config, "MULTI_CONNECTION_MIN_BYTES", 100), \
             patch("download_sources.probe_multi_connection_download", new_callable=AsyncMock, return_value=200), \
             patch("download_sources._download_single_file_multi_connection", new_callable=AsyncMock, return_value="book.zip") as multi, \
             patch("download_sources._download_single_file_stream", new_callable=AsyncMock) as stream:
            result = await download_sources.download_single_file("https://example.test/book.zip", "book.zip", progress)

        self.assertEqual(result, "book.zip")
        multi.assert_awaited_once_with("https://example.test/book.zip", "book.zip", 200, progress)
        stream.assert_not_awaited()

    async def test_falls_back_to_single_stream_when_multi_fails(self):
        progress = AsyncMock()
        with patch.object(config, "MULTI_CONNECTION_DOWNLOADS", True), \
             patch.object(config, "MULTI_CONNECTION_MIN_BYTES", 100), \
             patch("download_sources.probe_multi_connection_download", new_callable=AsyncMock, return_value=200), \
             patch("download_sources._download_single_file_multi_connection", new_callable=AsyncMock, return_value=None), \
             patch("download_sources._download_single_file_stream", new_callable=AsyncMock, return_value="book.zip") as stream:
            result = await download_sources.download_single_file("https://example.test/book.zip", "book.zip", progress)

        self.assertEqual(result, "book.zip")
        stream.assert_awaited_once_with("https://example.test/book.zip", "book.zip", progress)

    async def test_skips_multi_connection_when_probe_is_too_small(self):
        progress = AsyncMock()
        with patch.object(config, "MULTI_CONNECTION_DOWNLOADS", True), \
             patch.object(config, "MULTI_CONNECTION_MIN_BYTES", 100), \
             patch("download_sources.probe_multi_connection_download", new_callable=AsyncMock, return_value=99), \
             patch("download_sources._download_single_file_multi_connection", new_callable=AsyncMock) as multi, \
             patch("download_sources._download_single_file_stream", new_callable=AsyncMock, return_value="book.zip") as stream:
            result = await download_sources.download_single_file("https://example.test/book.zip", "book.zip", progress)

        self.assertEqual(result, "book.zip")
        multi.assert_not_awaited()
        stream.assert_awaited_once_with("https://example.test/book.zip", "book.zip", progress)


class TestByteRangeSplitting(unittest.TestCase):
    def test_build_byte_ranges_covers_file_without_overlap(self):
        ranges = download_sources.build_byte_ranges(10, 3)
        self.assertEqual(ranges, [(0, 2), (3, 5), (6, 9)])

    def test_build_byte_ranges_caps_segments_to_total_bytes(self):
        ranges = download_sources.build_byte_ranges(3, 8)
        self.assertEqual(ranges, [(0, 0), (1, 1), (2, 2)])


class TestMultiConnectionDownload(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest_path = os.path.join(self.tmp.name, "book.zip")
        self.progress = AsyncMock()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_multi_connection_download_combines_ordered_parts(self):
        FakeAsyncClient.responses = [
            FakeStreamResponse(
                headers={"content-range": "bytes 0-2/6"},
                chunks=[b"abc"],
            ),
            FakeStreamResponse(
                headers={"content-range": "bytes 3-5/6"},
                chunks=[b"def"],
            ),
        ]
        FakeAsyncClient.requested_ranges = []

        with patch.object(config, "MULTI_CONNECTION_MAX_SEGMENTS", 2), \
             patch.object(config, "MULTI_CONNECTION_MIN_BYTES", 3), \
             patch("download_sources.httpx.AsyncClient", FakeAsyncClient), \
             patch("download_sources.get_host_semaphore", new_callable=AsyncMock, return_value=download_sources.asyncio.Semaphore(2)):
            result = await download_sources._download_single_file_multi_connection(
                "https://example.test/book.zip",
                self.dest_path,
                6,
                self.progress,
            )

        self.assertEqual(result, self.dest_path)
        with open(self.dest_path, "rb") as f:
            self.assertEqual(f.read(), b"abcdef")
        self.assertEqual(FakeAsyncClient.requested_ranges, ["bytes=0-2", "bytes=3-5"])
        self.progress.assert_any_await(100.0, 6, 6, phase="downloading")

    async def test_multi_connection_download_cleans_partial_files_on_bad_range(self):
        FakeAsyncClient.responses = [
            FakeStreamResponse(
                headers={"content-range": "bytes 0-2/6"},
                chunks=[b"abc"],
            ),
            FakeStreamResponse(
                headers={"content-range": "bytes 4-5/6"},
                chunks=[b"ef"],
            ),
        ]
        FakeAsyncClient.requested_ranges = []

        with patch.object(config, "MULTI_CONNECTION_MAX_SEGMENTS", 2), \
             patch.object(config, "MULTI_CONNECTION_MIN_BYTES", 3), \
             patch("download_sources.httpx.AsyncClient", FakeAsyncClient), \
             patch("download_sources.get_host_semaphore", new_callable=AsyncMock, return_value=download_sources.asyncio.Semaphore(2)):
            result = await download_sources._download_single_file_multi_connection(
                "https://example.test/book.zip",
                self.dest_path,
                6,
                self.progress,
            )

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.dest_path))
        self.assertFalse(os.path.exists(f"{self.dest_path}.multi"))
        self.assertFalse(os.path.exists(f"{self.dest_path}.part0"))
        self.assertFalse(os.path.exists(f"{self.dest_path}.part1"))


if __name__ == "__main__":
    unittest.main()
