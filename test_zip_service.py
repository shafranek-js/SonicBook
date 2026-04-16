import asyncio
import os
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

if __name__ == '__main__':
    unittest.main()
