import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import sys

# Mock modules that might not be installed
sys.modules['yt_dlp'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['httpx'] = MagicMock()

import processor

class MockAioFile:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def write(self, data):
        pass

class TestRunFastDownload(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.task_id = "test_task"
        self.title_base = "Test Title"
        self.chapters = []
        self.mode = "m4b"
        self.progress_callback = AsyncMock()
        self.cover_url = None
        self.source_url = None

        # Patch prepare_task_work_dir
        self.patcher_prepare = patch('processor.prepare_task_work_dir', return_value="/tmp/test_dir")
        self.mock_prepare = self.patcher_prepare.start()

        processor.aiofiles.open = MagicMock(return_value=MockAioFile())

    async def asyncTearDown(self):
        self.patcher_prepare.stop()

    @patch('processor._handle_direct_urls_download', return_value=("source.mp3", ".mp3"))
    @patch('processor.os.path.exists', return_value=True)
    async def test_direct_urls(self, mock_exists, mock_handle):
        m3u8_url = "DIRECT_URLS:url1,url2"
        # Mock create_m4b_with_chapters/split_to_chapters shouldn't be called because chapters=[]

        with patch('processor.os.remove'), \
             patch('processor.shutil.rmtree'), patch('processor.asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
            async def to_thread_side_effect(func, *args, **kwargs):
                if func == processor.move_to_library:
                    return "/lib/source.mp3"
                return None
            mock_thread.side_effect = to_thread_side_effect

            result = await processor.run_fast_download(
                self.task_id, m3u8_url, self.title_base, self.chapters,
                self.mode, self.progress_callback, self.cover_url, self.source_url
            )

        mock_handle.assert_called_once()
        self.assertEqual(result, f"{self.title_base}.mp3")

    @patch('processor._handle_direct_zip_download', return_value=("source.zip", ".zip"))
    @patch('processor.os.path.exists', return_value=True)
    async def test_direct_zip(self, mock_exists, mock_handle):
        m3u8_url = "DIRECT_ZIP:http://test.zip"

        with patch('processor.os.remove'), \
             patch('processor.shutil.rmtree'), patch('processor.asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
            async def to_thread_side_effect(func, *args, **kwargs):
                if func == processor.move_to_library:
                    return "/lib/source.zip"
                return None
            mock_thread.side_effect = to_thread_side_effect

            result = await processor.run_fast_download(
                self.task_id, m3u8_url, self.title_base, self.chapters,
                self.mode, self.progress_callback, self.cover_url, self.source_url
            )

        mock_handle.assert_called_once()
        self.assertEqual(result, f"{self.title_base}.zip")

    @patch('processor._handle_ytdlp_download', return_value=("source.mp4", ".mp4"))
    @patch('processor.os.path.exists', return_value=True)
    async def test_ytdlp(self, mock_exists, mock_handle):
        m3u8_url = "http://test.m3u8"

        with patch('processor.os.remove'), \
             patch('processor.shutil.rmtree'), patch('processor.asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
            async def to_thread_side_effect(func, *args, **kwargs):
                if func == processor.move_to_library:
                    return "/lib/source.mp4"
                return None
            mock_thread.side_effect = to_thread_side_effect

            result = await processor.run_fast_download(
                self.task_id, m3u8_url, self.title_base, self.chapters,
                self.mode, self.progress_callback, self.cover_url, self.source_url
            )

        mock_handle.assert_called_once()
        self.assertEqual(result, f"{self.title_base}.mp4")

if __name__ == "__main__":
    unittest.main()
