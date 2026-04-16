import unittest
from unittest.mock import patch, AsyncMock, MagicMock

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

        self.patcher_prepare = patch('processor.prepare_task_work_dir', return_value="/tmp/test_dir")
        self.mock_prepare = self.patcher_prepare.start()
        
        self.patcher_aiofiles = patch('processor.aiofiles.open', return_value=MockAioFile())
        self.patcher_aiofiles.start()

    async def asyncTearDown(self):
        self.patcher_prepare.stop()
        self.patcher_aiofiles.stop()

    @patch('processor._handle_direct_urls_download', new_callable=AsyncMock)
    @patch('processor.os.path.exists', return_value=True)
    async def test_direct_urls(self, mock_exists, mock_handle):
        mock_handle.return_value = ("source.mp3", ".mp3")
        m3u8_url = "DIRECT_URLS:url1,url2"

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

    @patch('processor._handle_direct_zip_download', new_callable=AsyncMock)
    @patch('processor.os.path.exists', return_value=True)
    async def test_direct_zip(self, mock_exists, mock_handle):
        mock_handle.return_value = ("source.zip", ".zip")
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

    @patch('processor._handle_ytdlp_download', new_callable=AsyncMock)
    @patch('processor.os.path.exists', return_value=True)
    async def test_ytdlp(self, mock_exists, mock_handle):
        mock_handle.return_value = ("source.mp4", ".mp4")
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
