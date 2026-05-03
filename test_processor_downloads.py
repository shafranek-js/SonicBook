import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import tempfile

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


class TestRunFastDownloadMediaTransitions(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work_dir = os.path.join(self.tmp.name, "work")
        self.library_dir = os.path.join(self.tmp.name, "library")
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.library_dir, exist_ok=True)
        self.progress_callback = AsyncMock()
        self.chapters = [
            {"title": "Chapter 1", "start": 0.0, "end": 10.0},
            {"title": "Chapter 2", "start": 10.0, "end": 20.0},
        ]

        self.patcher_prepare = patch('processor.prepare_task_work_dir', return_value=self.work_dir)
        self.patcher_prepare.start()
        self.patcher_downloads = patch('processor.config.DOWNLOADS_DIR', self.library_dir)
        self.patcher_downloads.start()

    async def asyncTearDown(self):
        self.patcher_prepare.stop()
        self.patcher_downloads.stop()
        self.tmp.cleanup()

    async def _run_m4b_case(self, m3u8_url, source_name, source_ext, handler_name):
        source_path = os.path.join(self.work_dir, source_name)
        assembled_path = os.path.join(self.work_dir, "assembled.m4b")
        with open(source_path, "wb") as f:
            f.write(b"source")
        with open(assembled_path, "wb") as f:
            f.write(b"m4b")

        async def fake_create_m4b(source, chapters, title_base, task_id, work_dir, cover_path=None, progress_callback=None):
            self.assertEqual(source, source_path)
            self.assertEqual(chapters, self.chapters)
            self.assertEqual(title_base, "Media Book")
            self.assertEqual(task_id, "task-media")
            self.assertEqual(work_dir, self.work_dir)
            if progress_callback:
                await progress_callback(100.0)
            return assembled_path

        with patch(f'processor.{handler_name}', new_callable=AsyncMock) as mock_handler, \
             patch('processor.create_m4b_with_chapters', side_effect=fake_create_m4b) as mock_create:
            mock_handler.return_value = (source_path, source_ext)
            result = await processor.run_fast_download(
                "task-media",
                m3u8_url,
                "Media Book",
                self.chapters,
                "m4b",
                self.progress_callback,
                cover_url=None,
                source_url="https://example.test/book",
            )

        self.assertEqual(result, "Media Book.m4b")
        self.assertTrue(os.path.exists(os.path.join(self.library_dir, "Media Book.m4b")))
        self.assertTrue(os.path.exists(os.path.join(self.library_dir, "Media Book.json")))
        mock_create.assert_called_once()
        self.progress_callback.assert_any_await(0.0, 0, 100, status="assembling", phase="assembling")

    async def test_direct_mp3_urls_with_chapters_assemble_to_m4b(self):
        await self._run_m4b_case(
            "DIRECT_URLS:https://audio.example/001.mp3,https://audio.example/002.mp3",
            "merged_task-media.mp3",
            ".mp3",
            "_handle_direct_urls_download",
        )

    async def test_hls_mp4_output_with_chapters_assembles_to_m4b(self):
        await self._run_m4b_case(
            "https://stream.example/book.m3u8",
            "dl_task-media.mp4",
            ".mp4",
            "_handle_ytdlp_download",
        )


class TestCreateM4BWithChapters(unittest.IsolatedAsyncioTestCase):

    async def test_mp3_sources_are_transcoded_and_empty_outputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "source.mp3")
            with open(source_path, "wb") as f:
                f.write(b"mp3")

            captured = {}

            async def fake_run_ffmpeg(cmd, duration_seconds, progress_callback=None, timeout=3600):
                captured["cmd"] = cmd
                out_path = cmd[-1]
                open(out_path, "wb").close()
                return 0, b"", False

            with patch('processor.get_media_duration', new_callable=AsyncMock, return_value=10.0), \
                 patch('processor.run_ffmpeg_with_progress', side_effect=fake_run_ffmpeg):
                result = await processor.create_m4b_with_chapters(
                    source_path,
                    [{"title": "Only Chapter", "start": 0.0, "end": 10.0}],
                    "MP3 Book",
                    "task-mp3",
                    tmp,
                )

            self.assertIsNone(result)
            self.assertIn("-c:a", captured["cmd"])
            codec_index = captured["cmd"].index("-c:a") + 1
            self.assertEqual(captured["cmd"][codec_index], "aac")
            self.assertIn("-b:a", captured["cmd"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "out_task-mp3.m4b")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "meta_task-mp3.txt")))

    async def test_mp4_sources_copy_audio_for_m4b_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "source.mp4")
            with open(source_path, "wb") as f:
                f.write(b"mp4")

            captured = {}

            async def fake_run_ffmpeg(cmd, duration_seconds, progress_callback=None, timeout=3600):
                captured["cmd"] = cmd
                out_path = cmd[-1]
                with open(out_path, "wb") as f:
                    f.write(b"m4b")
                return 0, b"", False

            with patch('processor.get_media_duration', new_callable=AsyncMock, return_value=10.0), \
                 patch('processor.run_ffmpeg_with_progress', side_effect=fake_run_ffmpeg):
                result = await processor.create_m4b_with_chapters(
                    source_path,
                    [{"title": "Only Chapter", "start": 0.0, "end": 10.0}],
                    "MP4 Book",
                    "task-mp4",
                    tmp,
                )

            self.assertEqual(result, os.path.join(tmp, "out_task-mp4.m4b"))
            self.assertIn("-c:a", captured["cmd"])
            codec_index = captured["cmd"].index("-c:a") + 1
            self.assertEqual(captured["cmd"][codec_index], "copy")
            self.assertNotIn("-b:a", captured["cmd"])

if __name__ == "__main__":
    unittest.main()
