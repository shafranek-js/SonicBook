import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Mocking modules that are not available
mock_httpx = MagicMock()
sys.modules["httpx"] = mock_httpx

# Mocking aiofiles
mock_aiofiles = MagicMock()
sys.modules["aiofiles"] = mock_aiofiles

mock_PIL = MagicMock()
sys.modules["PIL"] = mock_PIL

import google_drive_service

class TestGoogleDriveServiceDownload(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_file = AsyncMock()
        self.mock_file_context = MagicMock()
        self.mock_file_context.__aenter__.return_value = self.mock_file
        mock_aiofiles.open.return_value = self.mock_file_context

    async def test_download_drive_file_to_path(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_client.get = AsyncMock(return_value=mock_response)

        file_id = "test_file_id"
        destination_path = "test_dest.bin"

        result = await google_drive_service._download_drive_file_to_path(mock_client, file_id, destination_path)

        self.assertEqual(result, destination_path)
        mock_client.get.assert_called_once()
        mock_aiofiles.open.assert_called_with(destination_path, "wb")
        self.mock_file.write.assert_called_with(b"test content")

    async def test_download_public_drive_file_to_path(self):
        file_id = "test_public_id"
        destination_path = "test_public_dest.bin"

        mock_client = MagicMock()
        mock_response = MagicMock()

        async def mock_aiter_bytes():
            yield b"chunk1"
            yield b"chunk2"

        mock_response.aiter_bytes = mock_aiter_bytes
        mock_response.aclose = AsyncMock()
        mock_client.aclose = AsyncMock()

        with patch("google_drive_service._open_public_drive_file", AsyncMock(return_value=(mock_client, mock_response))):
            result = await google_drive_service._download_public_drive_file_to_path(file_id, destination_path)

            self.assertEqual(result, destination_path)
            mock_aiofiles.open.assert_called_with(destination_path, "wb")
            self.assertEqual(self.mock_file.write.call_count, 2)
            self.mock_file.write.assert_any_call(b"chunk1")
            self.mock_file.write.assert_any_call(b"chunk2")
            mock_response.aclose.assert_called_once()
            mock_client.aclose.assert_called_once()

if __name__ == "__main__":
    unittest.main()
