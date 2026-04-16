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

    def test_normalize_book_name(self):
        self.assertEqual(bookmark_service._normalize_book_name("Test Book 123.mp3"), "test book 123")
        self.assertEqual(bookmark_service._normalize_book_name("  Test   Book  "), "test book")
        self.assertEqual(bookmark_service._normalize_book_name("Test_Book-Name"), "test_book name")

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

        # Test getting aliases via name, not via direct alias id
        # Let's save under a legacy id, then query under a new id.
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

    def test_build_legacy_book_id(self):
        self.assertEqual(bookmark_service.build_legacy_book_id("Test Book"), "book:test book")
        self.assertEqual(bookmark_service.build_legacy_book_id(""), "")
        self.assertEqual(bookmark_service.build_legacy_book_id(metadata={"title": "Test Book"}), "book:test book")

    def test_derive_aliases_from_book_id(self):
        self.assertEqual(bookmark_service._derive_aliases_from_book_id(""), [])
        self.assertEqual(bookmark_service._derive_aliases_from_book_id("invalid"), [])
        self.assertEqual(bookmark_service._derive_aliases_from_book_id("book:file:test:1024"), ["book:test", "book:file:test"])

    def test_build_book_id_aliases_with_name(self):
        aliases = bookmark_service.build_book_id_aliases(name="Test Book", size_bytes=1024)
        self.assertIn("book:file:test book:1024", aliases)
        self.assertIn("book:file:test book", aliases)
        self.assertIn("book:test book", aliases)

    def test_get_state_storage_status(self):
        status = bookmark_service.get_state_storage_status()
        self.assertEqual(status["profile_id"], "test_profile")
        self.assertEqual(status["configured_id"], "test")
        self.assertEqual(status["source"], "device")
        self.assertTrue("state_file" in status)
        self.assertTrue("legacy_state_file" in status)

    def test_load_json_file_exception(self):
        temp_file = os.path.join(self.temp_dir, "test.json")
        with open(temp_file, "w") as f:
            f.write("{}")
        with patch("builtins.open", side_effect=Exception("Read Error")):
            self.assertIsNone(bookmark_service._load_json_file(temp_file))

    def test_write_marker_file_exception(self):
        temp_file = os.path.join(self.temp_dir, "marker.txt")
        with patch("builtins.open", side_effect=Exception("Write Error")):
            bookmark_service._write_marker_file(temp_file)
            self.assertFalse(os.path.exists(temp_file))

    def test_normalize_last_active_non_dict(self):
        self.assertEqual(bookmark_service._normalize_last_active(None), {})
        self.assertEqual(bookmark_service._normalize_last_active([]), {})
        self.assertEqual(bookmark_service._normalize_last_active({"invalid": "data"}), {})

    def test_normalize_state_payload_legacy_flat(self):
        payload = {
            "book:test": {"time": 10, "duration": 100}
        }
        state = bookmark_service._normalize_state_payload(payload)
        self.assertEqual(state["bookmarks"]["book:test"]["time"], 10)
        self.assertEqual(state["updated_at"], 0)

        state_non_dict = bookmark_service._normalize_state_payload(None)
        self.assertEqual(state_non_dict["bookmarks"], {})

    def test_save_state_exception(self):
        with patch("bookmark_service._ensure_shared_state_dir", side_effect=Exception("Save Error")):
            # Even with exception, it should return False
            self.assertFalse(bookmark_service._save_state({"bookmarks": {}}))

        # test temp file cleanup
        state_path = bookmark_service._shared_state_file()
        temp_path = state_path + ".tmp"
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            f.write("test")

        with patch("builtins.open", side_effect=Exception("Save Error")):
            self.assertFalse(bookmark_service._save_state({"bookmarks": {}}))
            self.assertFalse(os.path.exists(temp_path))

        with open(temp_path, "w") as f:
            f.write("test")
        with patch("builtins.open", side_effect=Exception("Save Error")):
            with patch("os.remove", side_effect=OSError("Remove Error")):
                self.assertFalse(bookmark_service._save_state({"bookmarks": {}}))
                self.assertTrue(os.path.exists(temp_path))

    def test_migrate_legacy_bookmarks_if_needed_no_legacy_file(self):
        self.assertIsNone(bookmark_service._migrate_legacy_bookmarks_if_needed())

        # Test with marker existing
        marker_path = bookmark_service._legacy_migration_marker_file()
        bookmark_service._write_marker_file(marker_path)
        self.assertIsNone(bookmark_service._migrate_legacy_bookmarks_if_needed())

        # Remove marker
        os.remove(marker_path)

        # Create legacy shared state
        legacy_shared = bookmark_service._legacy_shared_state_file()
        os.makedirs(os.path.dirname(legacy_shared), exist_ok=True)
        with open(legacy_shared, "w") as f:
            json.dump({"book:shared": {"time": 1}}, f)

        migrated = bookmark_service._migrate_legacy_bookmarks_if_needed()
        self.assertIsNotNone(migrated)
        self.assertIn("book:shared", migrated["bookmarks"])
        self.assertTrue(os.path.exists(marker_path))

    def test_list_bookmarks(self):
        bookmark_service.save_bookmarks({"book:test": {"time": 10}})
        bookmarks = bookmark_service.list_bookmarks()
        self.assertIn("book:test", bookmarks)

    def test_save_last_active_errors(self):
        with self.assertRaises(RuntimeError):
            bookmark_service.save_last_active({})

        with patch("bookmark_service._save_state", return_value=False):
            with self.assertRaises(RuntimeError):
                bookmark_service.save_last_active({"book_id": "test"})

    def test_save_bookmark_edge_cases(self):
        with self.assertRaises(RuntimeError):
            bookmark_service.save_bookmark("", {})

        saved = bookmark_service.save_bookmark("book:edge", {
            "time": -10,
            "duration": -20,
            "track": -5,
            "completed": "1"
        })
        self.assertEqual(saved["time"], 0)
        self.assertEqual(saved["duration"], 0)
        self.assertEqual(saved["track"], 0)
        self.assertTrue(saved["completed"])

        saved2 = bookmark_service.save_bookmark("book:edge", {
            "completed": "invalid"
        })
        self.assertFalse(saved2["completed"])

        # Test replacing an alias bookmark
        # Manually save a bookmark under an alias
        bookmark_service.save_bookmarks({"book:file:replace": {"time": 5}})
        # Saving under new ID with aliases including the one we just saved
        bookmark_service.save_bookmark("book:file:replace:100", {"time": 20})
        bookmarks = bookmark_service.load_bookmarks()
        self.assertIn("book:file:replace:100", bookmarks)
        self.assertNotIn("book:file:replace", bookmarks)

        with patch("bookmark_service._save_state", return_value=False):
            with self.assertRaises(RuntimeError):
                bookmark_service.save_bookmark("book:edge", {})

    def test_delete_bookmark_edge_cases(self):
        self.assertFalse(bookmark_service.delete_bookmark(""))

        # Test unchanged state
        self.assertTrue(bookmark_service.delete_bookmark("book:nonexistent"))

        # Test active bookmark deletion
        bookmark_service.save_last_active({"book_id": "book:delete"})
        bookmark_service.save_bookmark("book:delete", {"time": 10})
        self.assertTrue(bookmark_service.delete_bookmark("book:delete"))

        state = bookmark_service.load_state()
        self.assertEqual(state["last_active"], {})

if __name__ == '__main__':
    unittest.main()
