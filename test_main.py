import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
import main

class TestMainUtilities(unittest.TestCase):
    def test_guess_media_type(self):
        self.assertEqual(main.guess_media_type("book.m4b"), "audio/mp4")
        self.assertEqual(main.guess_media_type("cover.jpg"), "image/jpeg")
        # unknown.xyz on some systems can be chemical/x-xyz, let's use a definitely unknown one
        self.assertEqual(main.guess_media_type("unknown.totallyunknownext"), "application/octet-stream")
        self.assertEqual(main.guess_media_type("doc.txt"), "text/plain")

    def test_build_inline_content_disposition(self):
        result = main.build_inline_content_disposition("/path/to/my book.m4b")
        self.assertEqual(result, "inline; filename*=utf-8''my%20book.m4b")

    def test_parse_range_header_none(self):
        self.assertIsNone(main.parse_range_header("", 100))
        self.assertIsNone(main.parse_range_header(None, 100))

    def test_parse_range_header_invalid_unit(self):
        with self.assertRaises(HTTPException) as ctx:
            main.parse_range_header("bits=0-10", 100)
        self.assertEqual(ctx.exception.status_code, 416)

        with self.assertRaises(HTTPException) as ctx:
            main.parse_range_header("bytes=", 100)
        self.assertEqual(ctx.exception.status_code, 416)

    def test_parse_range_header_invalid_format(self):
        with self.assertRaises(HTTPException) as ctx:
            main.parse_range_header("bytes=0", 100)
        self.assertEqual(ctx.exception.status_code, 416)

    def test_parse_range_header_valid(self):
        self.assertEqual(main.parse_range_header("bytes=0-499", 1000), (0, 499))
        self.assertEqual(main.parse_range_header("bytes=500-", 1000), (500, 999))
        self.assertEqual(main.parse_range_header("bytes=-500", 1000), (500, 999))

    def test_parse_range_header_out_of_bounds(self):
        with self.assertRaises(HTTPException) as ctx:
            main.parse_range_header("bytes=1000-2000", 1000)
        self.assertEqual(ctx.exception.status_code, 416)

    @patch("main.config")
    def test_resolve_download_path(self, mock_config):
        import os
        mock_config.DOWNLOADS_DIR = os.path.abspath("/mock/downloads")

        # Valid path
        result = main.resolve_download_path("book.m4b")
        # Handle cross-platform path slashes by normalizing expected
        expected = os.path.abspath(os.path.join(mock_config.DOWNLOADS_DIR, "book.m4b"))
        self.assertEqual(result, expected)

        # Invalid path: empty
        with self.assertRaises(HTTPException) as ctx:
            main.resolve_download_path("")
        self.assertEqual(ctx.exception.status_code, 400)

        # Invalid path: absolute
        with self.assertRaises(HTTPException) as ctx:
            main.resolve_download_path("/etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

        # Invalid path: traversal outside
        with self.assertRaises(HTTPException) as ctx:
            main.resolve_download_path("../etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_book_url(self):
        self.assertEqual(main.validate_book_url("https://example.com/book"), "https://example.com/book")
        self.assertEqual(main.validate_book_url("http://example.com"), "http://example.com")

        with self.assertRaises(HTTPException) as ctx:
            main.validate_book_url("ftp://example.com")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            main.validate_book_url("not a url")
        self.assertEqual(ctx.exception.status_code, 400)

class TestMainEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    @patch("main.config.DOWNLOADS_DIR", "/app/downloads")
    def test_get_folder(self):
        response = self.client.get("/api/settings/folder")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"folder": "/app/downloads"})

    @patch("main.config.get_playback_profile_status")
    @patch("main.bookmark_service.get_state_storage_status")
    def test_get_playback_profile(self, mock_state, mock_profile):
        mock_profile.return_value = {"profile_id": "test_profile"}
        mock_state.return_value = {"storage": "local"}

        response = self.client.get("/api/settings/playback-profile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"profile_id": "test_profile", "storage": "local"})

    @patch("main.scraper.get_book_info")
    def test_get_info_success(self, mock_get_book_info):
        import asyncio
        async def mock_info(*args, **kwargs):
            return "http://stream.m3u8", "Test Title", [{"title": "Chapter 1", "start": 0}], "http://cover.jpg"
        mock_get_book_info.side_effect = mock_info

        response = self.client.post("/api/info", json={"url": "https://example.com/book"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "title": "Test Title",
            "chapters": [{"title": "Chapter 1", "start": 0}],
            "cover": "http://cover.jpg"
        })

    @patch("main.scraper.get_book_info")
    def test_get_info_not_found(self, mock_get_book_info):
        async def mock_info(*args, **kwargs):
            return None, None, None, None
        mock_get_book_info.side_effect = mock_info

        response = self.client.post("/api/info", json={"url": "https://example.com/book"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Audio stream not found"})

    @patch("main.library_service.list_library_files")
    @patch("main.config.DOWNLOADS_DIR", "/mock/downloads")
    def test_get_library(self, mock_list_library_files):
        mock_list_library_files.return_value = ["book1.m4b", "book2.m4b"]
        response = self.client.get("/api/library")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"files": ["book1.m4b", "book2.m4b"]})
        mock_list_library_files.assert_called_once_with("/mock/downloads")


class TestDownloadMetadataEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    @patch("main.os.path.exists")
    @patch("main.os.path.getsize")
    @patch("main.resolve_download_path")
    def test_download_file_success(self, mock_resolve, mock_getsize, mock_exists):
        mock_resolve.return_value = "/mock/downloads/book.txt"
        mock_exists.return_value = True
        mock_getsize.return_value = 100

        # we can't easily mock FileResponse internals without it failing or reading from disk,
        # so let's mock it at the router level or test range request which we control

        # Test range request instead to avoid FileResponse actually opening the file synchronously
        with patch("main.iter_file_range") as mock_iter:
            async def mock_gen(*args, **kwargs):
                yield b"test"
            mock_iter.return_value = mock_gen()

            response = self.client.get("/api/files/book.txt", headers={"Range": "bytes=0-3"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.content, b"test")

    @patch("main.os.path.exists")
    @patch("main.resolve_download_path")
    def test_download_file_not_found(self, mock_resolve, mock_exists):
        mock_resolve.return_value = "/mock/downloads/book.txt"
        mock_exists.return_value = False

        response = self.client.get("/api/files/book.txt")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "File not found"})


class TestDownloadMetadata(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    @patch("main.zip_service.build_zip_metadata")
    @patch("main.bookmark_service.build_book_id")
    @patch("main.resolve_download_path")
    @patch("main.os.path.getsize")
    def test_get_metadata_zip(self, mock_getsize, mock_resolve, mock_build_book_id, mock_build_zip_metadata):
        mock_resolve.return_value = "/mock/downloads/playlist.zip"
        mock_build_zip_metadata.return_value = {"title": "Test Playlist", "chapters": []}
        mock_getsize.return_value = 1000
        mock_build_book_id.return_value = "mock_book_id"

        response = self.client.get("/api/metadata/playlist.zip")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"title": "Test Playlist", "chapters": [], "book_id": "mock_book_id"})

    @patch("main.os.path.exists")
    @patch("main.resolve_download_path")
    def test_get_metadata_not_found(self, mock_resolve, mock_exists):
        mock_resolve.return_value = "/mock/downloads/book.m4b"
        mock_exists.return_value = False

        response = self.client.get("/api/metadata/book.m4b")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Metadata not found"})


class TestDownloadEndpoint(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    @patch("main.progress_service.find_active_task_by_source")
    def test_start_download_existing(self, mock_find):
        mock_find.return_value = ("existing_task_id", {})
        with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
            response = self.client.post("/api/download", json={"url": "https://example.com/book", "mode": "m4b"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"task_id": "existing_task_id", "reused": True})

    @patch("main.progress_service.find_active_task_by_source")
    @patch("main.progress_service.set_progress")
    @patch("main.uuid.uuid4")
    def test_start_download_new(self, mock_uuid, mock_set_progress, mock_find):
        import uuid
        mock_find.return_value = None
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

        with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
            response = self.client.post("/api/download", json={"url": "https://example.com/book", "mode": "m4b"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"task_id": "12345678-1234-5678-1234-567812345678"})
        mock_set_progress.assert_called_once()


class TestBackgroundTasks(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    @patch("main.scraper.get_book_info")
    @patch("main.processor.run_fast_download")
    @patch("main.progress_service.update_progress_entry")
    def test_process_book_success(self, mock_update, mock_run, mock_get_info):
        import asyncio
        from main import process_book

        async def mock_info(*args, **kwargs):
            return "http://stream.m3u8", "Test Title", [{"title": "Chapter 1", "start": 0}], "http://cover.jpg"
        mock_get_info.side_effect = mock_info

        async def mock_download(*args, **kwargs):
            return "test_title.m4b"
        mock_run.side_effect = mock_download

        asyncio.run(process_book("task123", "https://example.com/book", "m4b"))

        # Verify it updated progress correctly
        mock_update.assert_any_call("task123", status="processing", phase="downloading", percent=0.0)
        mock_update.assert_any_call("task123", status="success", phase="complete", percent=100.0, file_name="test_title.m4b")

if __name__ == "__main__":
    unittest.main()
