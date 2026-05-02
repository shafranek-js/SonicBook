import os
import tempfile
import zipfile
import unittest
from unittest.mock import patch

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


class TestZipExtractionSafety(unittest.TestCase):
    def _build_zip(self, zip_path: str, member_name: str, content: str = "hello") -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr(member_name, content)

    def test_extract_zip_archive_rejects_dotdot_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "malicious.zip")
            extract_dir = os.path.join(tmp, "out")
            self._build_zip(zip_path, "../escape.txt")

            with self.assertRaises(ValueError):
                zip_service.extract_zip_archive(zip_path, extract_dir)

    def test_extract_zip_archive_rejects_backslash_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "malicious_backslash.zip")
            extract_dir = os.path.join(tmp, "out")
            self._build_zip(zip_path, "..\\escape.txt")

            with self.assertRaises(ValueError):
                zip_service.extract_zip_archive(zip_path, extract_dir)

    def test_extract_zip_archive_rejects_absolute_member_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "malicious_abs.zip")
            extract_dir = os.path.join(tmp, "out")
            absolute_member = os.path.abspath(os.path.join(tmp, "escape.txt"))
            self._build_zip(zip_path, absolute_member)

            with self.assertRaises(ValueError):
                zip_service.extract_zip_archive(zip_path, extract_dir)

    def test_extract_zip_archive_allows_normal_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "safe.zip")
            extract_dir = os.path.join(tmp, "out")
            self._build_zip(zip_path, "chapter1.mp3", "audio")

            zip_service.extract_zip_archive(zip_path, extract_dir)

            self.assertTrue(os.path.exists(os.path.join(extract_dir, "chapter1.mp3")))


if __name__ == "__main__":
    unittest.main()
