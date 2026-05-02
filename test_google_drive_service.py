import unittest
from unittest.mock import patch
import google_drive_service
import time
import os
import json
import tempfile

class TestGoogleDriveService(unittest.TestCase):
    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_ID', 'test_client_id')
    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_SECRET', 'test_client_secret')
    @patch('google_drive_service.GOOGLE_DRIVE_REDIRECT_URI', 'http://localhost/callback')
    def test_is_google_drive_configured_true(self):
        self.assertTrue(google_drive_service.is_google_drive_configured())

    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_ID', '')
    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_SECRET', 'test_client_secret')
    @patch('google_drive_service.GOOGLE_DRIVE_REDIRECT_URI', 'http://localhost/callback')
    def test_is_google_drive_configured_false_missing_client_id(self):
        self.assertFalse(google_drive_service.is_google_drive_configured())

    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_ID', 'test_client_id')
    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_SECRET', '')
    @patch('google_drive_service.GOOGLE_DRIVE_REDIRECT_URI', 'http://localhost/callback')
    def test_is_google_drive_configured_false_missing_client_secret(self):
        self.assertFalse(google_drive_service.is_google_drive_configured())

    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_ID', 'test_client_id')
    @patch('google_drive_service.GOOGLE_DRIVE_CLIENT_SECRET', 'test_client_secret')
    @patch('google_drive_service.GOOGLE_DRIVE_REDIRECT_URI', '')
    def test_is_google_drive_configured_false_missing_redirect_uri(self):
        self.assertFalse(google_drive_service.is_google_drive_configured())

    def test_extract_google_drive_folder_id(self):
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("1A2B3C4D5E6F7G8H9I0J_K-L"), "1A2B3C4D5E6F7G8H9I0J_K-L")
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I0J_K-L?usp=sharing"), "1A2B3C4D5E6F7G8H9I0J_K-L")
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I0J_K-L"), "1A2B3C4D5E6F7G8H9I0J_K-L")
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("https://drive.google.com/open?id=1A2B3C4D5E6F7G8H9I0J_K-L"), "1A2B3C4D5E6F7G8H9I0J_K-L")
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("https://drive.google.com/open?folder_id=1A2B3C4D5E6F7G8H9I0J_K-L"), "1A2B3C4D5E6F7G8H9I0J_K-L")

        self.assertEqual(google_drive_service.extract_google_drive_folder_id(""), "")
        self.assertEqual(google_drive_service.extract_google_drive_folder_id("  "), "")

        # Test invalid links
        with self.assertRaises(RuntimeError):
            google_drive_service.extract_google_drive_folder_id("https://example.com/folders/1A2B3C4D5E6F7G8H9I0J_K-L")

        with self.assertRaises(RuntimeError):
            # Missing ID completely
            google_drive_service.extract_google_drive_folder_id("https://drive.google.com/drive/folders/")

    def test_guess_drive_mime_type(self):
        self.assertEqual(google_drive_service._guess_drive_mime_type("book.m4b"), "audio/mp4")
        self.assertEqual(google_drive_service._guess_drive_mime_type("song.mp3"), "audio/mpeg")
        self.assertEqual(google_drive_service._guess_drive_mime_type("archive.zip"), "application/zip")
        self.assertEqual(google_drive_service._guess_drive_mime_type("cover.jpg"), "image/jpeg")
        self.assertEqual(google_drive_service._guess_drive_mime_type("data.json"), "application/json")
        self.assertEqual(google_drive_service._guess_drive_mime_type("unknown.bin"), "application/octet-stream")
        self.assertEqual(google_drive_service._guess_drive_mime_type("no_extension"), "application/octet-stream")

    @patch('google_drive_service.time.time', return_value=1700000000) # Nov 14, 2023
    @patch('google_drive_service.datetime')
    def test_parse_public_modified_label(self, mock_datetime, mock_time):
        from datetime import datetime
        mock_datetime.strptime = datetime.strptime
        mock_datetime.now.return_value = datetime(2023, 11, 14)

        # Test full date
        self.assertEqual(google_drive_service._parse_public_modified_label("Nov 10, 2023"), datetime(2023, 11, 10).timestamp())
        self.assertEqual(google_drive_service._parse_public_modified_label("November 10, 2023"), datetime(2023, 11, 10).timestamp())

        # Test short date (current year)
        self.assertEqual(google_drive_service._parse_public_modified_label("Nov 10"), datetime(2023, 11, 10).timestamp())

        # Test short date (previous year because it's in the future for current year)
        self.assertEqual(google_drive_service._parse_public_modified_label("Dec 20"), datetime(2022, 12, 20).timestamp())

        # Empty string
        self.assertEqual(google_drive_service._parse_public_modified_label(""), 0.0)

        # Invalid format
        self.assertEqual(google_drive_service._parse_public_modified_label("Invalid Date Format"), 0.0)

    def test_parse_google_timestamp(self):
        # Valid ISO format with Z
        from datetime import datetime
        expected = datetime.fromisoformat("2023-11-14T12:00:00+00:00").timestamp()
        self.assertEqual(google_drive_service._parse_google_timestamp("2023-11-14T12:00:00Z"), expected)

        # Fallback to public modified label
        with patch('google_drive_service._parse_public_modified_label', return_value=123.0) as mock_fallback:
            self.assertEqual(google_drive_service._parse_google_timestamp("Nov 10, 2023"), 123.0)
            mock_fallback.assert_called_once_with("Nov 10, 2023")

        # Empty string
        self.assertEqual(google_drive_service._parse_google_timestamp(""), 0.0)

    def test_extract_file_id_from_href(self):
        self.assertEqual(google_drive_service._extract_file_id_from_href("https://drive.google.com/file/d/1A2B3C/view"), "1A2B3C")
        self.assertEqual(google_drive_service._extract_file_id_from_href("/file/d/1A2B3C/view"), "1A2B3C")
        self.assertEqual(google_drive_service._extract_file_id_from_href("https://example.com/no-d-segment"), "")
        self.assertEqual(google_drive_service._extract_file_id_from_href("https://drive.google.com/file/d/"), "")


    def test_is_google_drive_public_link_mode(self):
        # Connected, so not public mode
        status1 = {"folder_id": "123", "connected": True}
        self.assertFalse(google_drive_service.is_google_drive_public_link_mode(status1))

        # Not connected, but has folder_id -> public mode
        status2 = {"folder_id": "123", "connected": False}
        self.assertTrue(google_drive_service.is_google_drive_public_link_mode(status2))

        # Not connected, no folder_id -> not public mode
        status3 = {"folder_id": "", "connected": False}
        self.assertFalse(google_drive_service.is_google_drive_public_link_mode(status3))

        # Missing folder_id
        status4 = {"connected": False}
        self.assertFalse(google_drive_service.is_google_drive_public_link_mode(status4))


    def test_extract_size_from_headers(self):
        # Range header with size
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-range": "bytes 0-0/12345"}), 12345)
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-range": "bytes */12345"}), 12345)

        # Content length
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-length": "67890"}), 67890)

        # Priority to content-range if both are present
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-range": "bytes 0-0/12345", "content-length": "1"}), 12345)

        # Invalid content-range fallback to content-length
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-range": "bytes 0-0/invalid", "content-length": "67890"}), 67890)

        # No valid size headers
        self.assertEqual(google_drive_service._extract_size_from_headers({}), 0)
        self.assertEqual(google_drive_service._extract_size_from_headers({"content-length": "invalid"}), 0)

    @patch('google_drive_service._drive_library_cache', {})
    def test_find_cached_drive_item(self):
        # Empty cache
        self.assertIsNone(google_drive_service._find_cached_drive_item("folder1", "file1"))

        # Populate cache
        google_drive_service._drive_library_cache["oauth:folder1"] = {
            "files": [
                {"drive_file_id": "file1", "name": "Test File 1"},
                {"drive_file_id": "file2", "name": "Test File 2"}
            ]
        }

        # Found in oauth cache
        item = google_drive_service._find_cached_drive_item("folder1", "file1")
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "Test File 1")

        # Not found in cache
        self.assertIsNone(google_drive_service._find_cached_drive_item("folder1", "file3"))

        # Missing folder or file
        self.assertIsNone(google_drive_service._find_cached_drive_item("", "file1"))
        self.assertIsNone(google_drive_service._find_cached_drive_item("folder1", ""))

    def test_public_stream_url(self):
        # Without resource key
        self.assertEqual(google_drive_service._public_stream_url("123"), "/api/google-drive/files/123/stream")

        # With resource key
        self.assertEqual(google_drive_service._public_stream_url("123", "abc"), "/api/google-drive/files/123/stream?resource_key=abc")

        # Empty file ID
        self.assertEqual(google_drive_service._public_stream_url(""), "")


class TestGoogleDriveOAuthStatePersistence(unittest.TestCase):
    def test_build_auth_url_persists_state_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "oauth_state.json")
            with patch("google_drive_service.GOOGLE_OAUTH_STATE_FILE", state_file), \
                 patch("google_drive_service.GOOGLE_DRIVE_CLIENT_ID", "client"), \
                 patch("google_drive_service.GOOGLE_DRIVE_CLIENT_SECRET", "secret"), \
                 patch("google_drive_service.GOOGLE_DRIVE_REDIRECT_URI", "http://127.0.0.1/callback"):
                google_drive_service._oauth_state_store = {}
                payload = google_drive_service.build_google_drive_auth_url()

            self.assertIn("state", payload)
            self.assertTrue(os.path.exists(state_file))
            with open(state_file, "r", encoding="utf-8") as f:
                stored = json.load(f)
            self.assertIn(payload["state"], stored.get("states", {}))

    def test_pop_valid_state_works_after_memory_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "oauth_state.json")
            now_ts = int(time.time())
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"states": {"abc": {"created_at": now_ts}}}, f)

            with patch("google_drive_service.GOOGLE_OAUTH_STATE_FILE", state_file):
                google_drive_service._oauth_state_store = {}
                payload = google_drive_service._pop_valid_state("abc")

            self.assertIsNotNone(payload)
            self.assertEqual(int(payload.get("created_at") or 0), now_ts)

    def test_expired_state_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "oauth_state.json")
            now_ts = int(time.time())
            expired_created_at = now_ts - (google_drive_service.GOOGLE_OAUTH_STATE_TTL_SECONDS + 5)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"states": {"expired": {"created_at": expired_created_at}}}, f)

            with patch("google_drive_service.GOOGLE_OAUTH_STATE_FILE", state_file):
                google_drive_service._oauth_state_store = {}
                payload = google_drive_service._pop_valid_state("expired")

            self.assertIsNone(payload)
            self.assertFalse(os.path.exists(state_file))

if __name__ == '__main__':
    unittest.main()
