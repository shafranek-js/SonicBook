import unittest
from unittest.mock import patch
import os
import json
import tempfile
import shutil

import bookmark_service

class TestBookmarkService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher1 = patch('config.DOWNLOADS_DIR', self.temp_dir)
        self.patcher2 = patch('config.get_playback_profile_status')
        self.patcher3 = patch('config.BASE_DIR', self.temp_dir)
        self.mock_downloads_dir = self.patcher1.start()
        self.mock_get_profile = self.patcher2.start()
        self.mock_base_dir = self.patcher3.start()

        self.mock_get_profile.return_value = {
            "profile_id": "test_profile",
            "configured_id": "test",
            "source": "device"
        }

        # Ensure modules constants that rely on patched globals are recreated
        bookmark_service.LEGACY_BOOKMARKS_FILE = os.path.join(self.temp_dir, "bookmarks.json")
        bookmark_service.STATE_FILE_NAME = "playback_state.json"

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        shutil.rmtree(self.temp_dir)

    def test_normalize_book_name_standard(self):
        self.assertEqual(bookmark_service._normalize_book_name("The Great Gatsby"), "the great gatsby")
        self.assertEqual(bookmark_service._normalize_book_name("Test Book 123.mp3"), "test book 123")
        self.assertEqual(bookmark_service._normalize_book_name("  Test   Book  "), "test book")
        self.assertEqual(bookmark_service._normalize_book_name("Test_Book-Name"), "test_book name")

    def test_normalize_book_name_with_extension(self):
        self.assertEqual(bookmark_service._normalize_book_name("The Great Gatsby.mp3"), "the great gatsby")
        self.assertEqual(bookmark_service._normalize_book_name("book_name.m4b"), "book_name")

    def test_normalize_book_name_special_chars(self):
        self.assertEqual(bookmark_service._normalize_book_name("Book-Name! @With# Special$ Characters%"), "book name with special characters")
        self.assertEqual(bookmark_service._normalize_book_name("Book_Name_With_Underscores"), "book_name_with_underscores") # \w includes underscores

    def test_normalize_book_name_unicode(self):
        self.assertEqual(bookmark_service._normalize_book_name("Толстой - Война и мир.mp3"), "толстой война и мир")
        self.assertEqual(bookmark_service._normalize_book_name("L'Étranger"), "l étranger")

    def test_normalize_book_name_extra_spaces(self):
        self.assertEqual(bookmark_service._normalize_book_name("  Book   with    spaces  "), "book with spaces")

    def test_normalize_book_name_empty(self):
        self.assertEqual(bookmark_service._normalize_book_name(""), "")
        self.assertEqual(bookmark_service._normalize_book_name(None), "")

    def test_normalize_book_name_path(self):
        self.assertEqual(bookmark_service._normalize_book_name("/path/to/some/Book Name.mp3"), "book name")

    def test_build_book_id(self):
        self.assertEqual(bookmark_service.build_book_id("Test Book", 1024), "book:file:test book:1024")
        self.assertEqual(bookmark_service.build_book_id("Test Book", None), "book:file:test book")
        self.assertEqual(bookmark_service.build_book_id(""), "")

    def test_build_book_id_aliases(self):
        aliases = bookmark_service.build_book_id_aliases(book_id="book:file:test book:1024")
        self.assertIn("book:file:test book:1024", aliases)
        self.assertIn("book:file:test book", aliases)
        self.assertIn("book:test book", aliases)

    def test_profile_storage_slug(self):
        slug1 = bookmark_service._profile_storage_slug("test_profile")
        slug2 = bookmark_service._profile_storage_slug("Test_Profile ")
        self.assertEqual(slug1, slug2)
        self.assertTrue(slug1.startswith("test_profile"))

        device_slug = bookmark_service._profile_storage_slug("")
        self.assertTrue(device_slug.startswith("device"))

    def test_load_save_state_empty(self):
        state = bookmark_service.load_state()
        self.assertEqual(state["version"], bookmark_service.STATE_VERSION)
        self.assertEqual(state["bookmarks"], {})
        self.assertEqual(state["last_active"], {})

    def test_save_and_load_bookmark(self):
        book_id = "book:file:test book:1024"
        payload = {
            "time": 10.5,
            "duration": 100.0,
            "track": 1,
            "file_name": "test.mp3",
            "source": "device",
            "completed": False
        }

        saved = bookmark_service.save_bookmark(book_id, payload)
        self.assertEqual(saved["time"], 10.5)
        self.assertEqual(saved["duration"], 100.0)
        self.assertEqual(saved["completed"], False)

        bookmark = bookmark_service.get_bookmark(book_id)
        self.assertIsNotNone(bookmark)
        self.assertEqual(bookmark["time"], 10.5)

        bookmark_service.save_bookmarks({"book:test legacy book": payload})
        self.assertIsNotNone(bookmark_service.get_bookmark("book:file:test legacy book:2048"))

    def test_save_bookmark_completed_logic(self):
        book_id = "book:file:completed book:1024"

        # Auto-complete based on time/duration
        payload1 = {"time": 99.6, "duration": 100.0}
        saved1 = bookmark_service.save_bookmark(book_id, payload1)
        self.assertTrue(saved1["completed"])

        # Explicitly marked not completed
        payload2 = {"time": 99.6, "duration": 100.0, "completed": "false"}
        saved2 = bookmark_service.save_bookmark(book_id, payload2)
        self.assertFalse(saved2["completed"])

    def test_delete_bookmark(self):
        # Let's create a bookmark under a specific ID
        book_id = "book:file:delete book:1024"
        bookmark_service.save_bookmark(book_id, {"time": 10})

        # Ensure it exists
        self.assertIsNotNone(bookmark_service.get_bookmark(book_id))

        self.assertTrue(bookmark_service.delete_bookmark(book_id))

        # Ensure it's gone
        self.assertIsNone(bookmark_service.get_bookmark(book_id))

    def test_save_and_load_last_active(self):
        payload = {
            "book_id": "book:file:active:100",
            "file_name": "active.mp3",
            "source": "device",
            "size_bytes": 100
        }

        saved = bookmark_service.save_last_active(payload)
        self.assertEqual(saved["book_id"], "book:file:active:100")
        self.assertTrue("updated_at" in saved)

        loaded = bookmark_service.get_last_active()
        self.assertEqual(loaded["book_id"], "book:file:active:100")

        bookmark_service.clear_last_active()
        cleared = bookmark_service.get_last_active()
        self.assertEqual(cleared, {})

    def test_legacy_migration(self):
        # Create legacy bookmarks file
        legacy_bookmarks = {
            "book:legacy book": {
                "time": 50,
                "duration": 100
            }
        }
        with open(bookmark_service.LEGACY_BOOKMARKS_FILE, "w") as f:
            json.dump(legacy_bookmarks, f)

        # Loading state should trigger migration
        state = bookmark_service.load_state()
        self.assertIn("book:legacy book", state["bookmarks"])
        self.assertEqual(state["bookmarks"]["book:legacy book"]["time"], 50)

        # Migration marker should be created
        self.assertTrue(os.path.exists(bookmark_service._legacy_migration_marker_file()))

        # Shared state file should be created
        self.assertTrue(os.path.exists(bookmark_service._shared_state_file()))

if __name__ == '__main__':
    unittest.main()
