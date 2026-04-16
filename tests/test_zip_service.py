import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys

# Mocking external dependencies that are not in the environment
class MockHTTPException(Exception):
    def __init__(self, status_code, detail=None):
        self.status_code = status_code
        self.detail = detail

fastapi_mock = MagicMock()
fastapi_mock.HTTPException = MockHTTPException
sys.modules["fastapi"] = fastapi_mock
sys.modules["library_service"] = MagicMock()

import zip_service
from fastapi import HTTPException

class TestZipService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        zip_service.zip_extraction_locks.clear()

    def test_get_zip_extraction_lock(self):
        lock1 = zip_service.get_zip_extraction_lock("test1")
        lock2 = zip_service.get_zip_extraction_lock("test1")
        lock3 = zip_service.get_zip_extraction_lock("test2")

        self.assertIsInstance(lock1, asyncio.Lock)
        self.assertIs(lock1, lock2)
        self.assertIsNot(lock1, lock3)

    @patch("zipfile.ZipFile")
    def test_extract_zip_archive(self, mock_zipfile):
        mock_archive = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_archive

        zip_service.extract_zip_archive("test.zip", "extract_dir")

        mock_zipfile.assert_called_once_with("test.zip", "r")
        mock_archive.extractall.assert_called_once_with("extract_dir")

    @patch("os.path.exists")
    @patch("asyncio.to_thread")
    async def test_ensure_zip_extracted_already_exists(self, mock_to_thread, mock_exists):
        mock_exists.return_value = True

        await zip_service.ensure_zip_extracted("test.zip", "dir_name", "dir_path")

        mock_to_thread.assert_not_called()

    @patch("os.path.exists")
    @patch("asyncio.to_thread")
    async def test_ensure_zip_extracted_needs_extraction(self, mock_to_thread, mock_exists):
        # First call to exists returns False, second (inside lock) returns False
        mock_exists.side_effect = [False, False]

        await zip_service.ensure_zip_extracted("test.zip", "dir_name", "dir_path")

        mock_to_thread.assert_called_once_with(zip_service.extract_zip_archive, "test.zip", "dir_path")

    @patch("os.path.exists")
    @patch("asyncio.to_thread")
    async def test_ensure_zip_extracted_double_check(self, mock_to_thread, mock_exists):
        # First call to exists returns False, second (inside lock) returns True (another thread finished it)
        mock_exists.side_effect = [False, True]

        await zip_service.ensure_zip_extracted("test.zip", "dir_name", "dir_path")

        mock_to_thread.assert_not_called()

    @patch("os.path.exists")
    @patch("asyncio.to_thread")
    async def test_ensure_zip_extracted_failure(self, mock_to_thread, mock_exists):
        mock_exists.return_value = False
        mock_to_thread.side_effect = Exception("Extraction failed")

        with self.assertRaises(HTTPException) as cm:
            await zip_service.ensure_zip_extracted("test.zip", "dir_name", "dir_path")

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.detail, "Failed to extract ZIP for playback")

    @patch("os.path.exists")
    @patch("zip_service.ensure_zip_extracted", new_callable=AsyncMock)
    @patch("os.listdir")
    @patch("library_service.load_sidecar_metadata")
    async def test_build_zip_metadata_missing_zip(self, mock_load_sidecar, mock_listdir, mock_ensure, mock_exists):
        mock_exists.return_value = False

        with self.assertRaises(HTTPException) as cm:
            await zip_service.build_zip_metadata("test.zip", "test.zip", "downloads")

        self.assertEqual(cm.exception.status_code, 404)

    @patch("os.path.exists")
    @patch("zip_service.ensure_zip_extracted", new_callable=AsyncMock)
    @patch("os.listdir")
    @patch("library_service.load_sidecar_metadata")
    async def test_build_zip_metadata_success(self, mock_load_sidecar, mock_listdir, mock_ensure, mock_exists):
        # os.path.exists for zip file is True, for extract_dir is True (after ensure_zip_extracted)
        mock_exists.return_value = True
        mock_listdir.return_value = ["c.mp3", "a.mp3", "b.txt", "d.m4a"]
        mock_load_sidecar.return_value = None

        result = await zip_service.build_zip_metadata("downloads/test.zip", "test.zip", "downloads")

        self.assertEqual(result["title"], "test")
        self.assertEqual(result["mode"], "zip")
        # Should only include audio files and be sorted
        self.assertEqual(len(result["playlist"]), 3)
        self.assertEqual(result["playlist"][0]["title"], "a")
        self.assertEqual(result["playlist"][1]["title"], "c")
        self.assertEqual(result["playlist"][2]["title"], "d")

        mock_ensure.assert_called_once()

    @patch("os.path.exists")
    @patch("zip_service.ensure_zip_extracted", new_callable=AsyncMock)
    @patch("os.listdir")
    @patch("library_service.load_sidecar_metadata")
    async def test_build_zip_metadata_with_sidecar(self, mock_load_sidecar, mock_listdir, mock_ensure, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["track1.mp3"]
        sidecar = {
            "title": "Override Title",
            "cover_url": "http://example.com/cover.jpg",
            "local_cover": "cover.jpg",
            "file_name": "original.zip"
        }
        mock_load_sidecar.return_value = sidecar

        result = await zip_service.build_zip_metadata("downloads/test.zip", "test.zip", "downloads")

        self.assertEqual(result["title"], "Override Title")
        self.assertEqual(result["cover_url"], "http://example.com/cover.jpg")
        self.assertEqual(result["local_cover"], "cover.jpg")
        self.assertEqual(result["file_name"], "original.zip")

if __name__ == "__main__":
    unittest.main()
