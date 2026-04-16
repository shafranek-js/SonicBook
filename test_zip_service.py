import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException

import zip_service

class TestZipService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        zip_service.zip_extraction_locks.clear()

    @patch("zip_service.os.path.exists")
    @patch("zip_service.extract_zip_archive")
    async def test_ensure_zip_extracted_exception_path(self, mock_extract, mock_exists):
        # We need os.path.exists to return False to enter the block.
        mock_exists.return_value = False

        # We want extract_zip_archive to raise an exception
        mock_extract.side_effect = Exception("Mocked extraction error")

        zip_path = "dummy.zip"
        extract_dir_name = "extracted_dummy"
        extract_dir_path = "/path/to/extracted_dummy"

        with self.assertRaises(HTTPException) as context:
            await zip_service.ensure_zip_extracted(zip_path, extract_dir_name, extract_dir_path)

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Failed to extract ZIP for playback")

    @patch("zip_service.zipfile.ZipFile")
    def test_extract_zip_archive_malicious_path(self, mock_zipfile):
        mock_archive = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_archive

        mock_member = MagicMock()
        mock_member.filename = "../../../etc/passwd"
        mock_archive.infolist.return_value = [mock_member]

        with self.assertRaises(ValueError) as context:
            zip_service.extract_zip_archive("dummy.zip", "/path/to/extract")

        self.assertIn("Malicious member path detected", str(context.exception))

    @patch("zip_service.zipfile.ZipFile")
    def test_extract_zip_archive_success(self, mock_zipfile):
        mock_archive = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_archive

        mock_member = MagicMock()
        mock_member.filename = "safe_file.txt"
        mock_archive.infolist.return_value = [mock_member]

        zip_service.extract_zip_archive("dummy.zip", "/path/to/extract")

        mock_archive.extractall.assert_called_once_with("/path/to/extract")

if __name__ == '__main__':
    unittest.main()
