import unittest
import time
import os
import json
import tempfile
from unittest.mock import patch
import progress_service

class TestProgressService(unittest.TestCase):
    """
    Tests for progress_service.py covering CRUD operations on the progress store,
    expiry cleanup, active task lookups, and deepcopy safety (preventing cache poisoning).
    """

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._store_file_patcher = patch.object(
            progress_service,
            "PROGRESS_STORE_FILE",
            os.path.join(self._temp_dir.name, "progress_store.json"),
        )
        self._store_file_patcher.start()
        # Clear the global store before each test to ensure isolation
        progress_service.progress_store.clear()
        progress_service._progress_store_dirty = False
        progress_service._progress_store_last_flush_at = 0.0

    def tearDown(self):
        self._store_file_patcher.stop()
        self._temp_dir.cleanup()

    def test_create_progress_entry(self):
        """Test basic creation of a progress entry with default fields."""
        url = "http://example.com/audiobook"
        mode = "m4b"
        entry = progress_service.create_progress_entry(url, mode)

        self.assertEqual(entry["status"], "searching")
        self.assertEqual(entry["phase"], "searching")
        self.assertEqual(entry["percent"], 0.0)
        self.assertEqual(entry["source_url"], url)
        self.assertEqual(entry["mode"], mode)
        self.assertIn("timestamp", entry)
        self.assertIsInstance(entry["timestamp"], float)

    def test_get_progress_not_found(self):
        """Test that non-existent tasks return a 'not_found' status."""
        result = progress_service.get_progress("non-existent-id")
        self.assertEqual(result, {"status": "not_found"})

    def test_set_and_get_progress(self):
        """Test basic CRUD: set and then retrieve a progress entry."""
        task_id = "task-123"
        payload = {"status": "processing", "percent": 45.5, "phase": "downloading"}
        progress_service.set_progress(task_id, payload)

        result = progress_service.get_progress(task_id)
        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["percent"], 45.5)
        self.assertEqual(result["phase"], "downloading")

    def test_update_progress_entry(self):
        """Test updating specific fields in an existing progress entry."""
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            task_id = "task-update"

            # Initial set
            entry = progress_service.create_progress_entry("http://url")
            progress_service.set_progress(task_id, entry)
            self.assertEqual(entry["timestamp"], 1000.0)

            # Update
            mock_time.return_value = 1005.0
            updated = progress_service.update_progress_entry(task_id, percent=80.0, status="assembling")

            self.assertIsNotNone(updated)
            self.assertEqual(updated["percent"], 80.0)
            self.assertEqual(updated["status"], "assembling")
            self.assertEqual(updated["timestamp"], 1005.0)

            # Verify persistence in store
            stored = progress_service.get_progress(task_id)
            self.assertEqual(stored["percent"], 80.0)

    def test_update_progress_entry_non_existent(self):
        """Test that updating a non-existent task returns None."""
        result = progress_service.update_progress_entry("missing-task", percent=50.0)
        self.assertIsNone(result)

    def test_cleanup_expired_progress(self):
        """Test that only terminal and expired tasks are cleaned up."""
        with patch("time.time") as mock_time:
            mock_time.return_value = 2000.0

            # 1. Active task (not terminal) - should NOT be deleted
            progress_service.set_progress("active", {"status": "downloading", "timestamp": 1000.0})

            # 2. Terminal task, NOT expired - should NOT be deleted
            progress_service.set_progress("recent_success", {"status": "success", "timestamp": 1950.0})

            # 3. Terminal task, EXPIRED - SHOULD be deleted
            progress_service.set_progress("old_error", {"status": "error", "timestamp": 1800.0})

            # Cleanup with 100s expiry (2000 - 1800 = 200 > 100)
            deleted = progress_service.cleanup_expired_progress(100)

            self.assertEqual(deleted, ["old_error"])
            self.assertNotIn("old_error", progress_service.progress_store)
            self.assertIn("active", progress_service.progress_store)
            self.assertIn("recent_success", progress_service.progress_store)

    def test_find_active_task_by_source(self):
        """Test looking up an active (non-terminal) task by its source URL."""
        url = "http://target-url.com"

        # 1. URL not in store
        self.assertIsNone(progress_service.find_active_task_by_source(url))

        # 2. Terminal task exists for URL - should return None as it is not 'active'
        progress_service.set_progress("task-done", {"source_url": url, "status": "success"})
        self.assertIsNone(progress_service.find_active_task_by_source(url))

        # 3. Active task exists for URL - should return the task info
        progress_service.set_progress("task-active", {"source_url": url, "status": "downloading"})
        result = progress_service.find_active_task_by_source(url)
        self.assertIsNotNone(result)
        tid, data = result
        self.assertEqual(tid, "task-active")
        self.assertEqual(data["status"], "downloading")

    def test_deep_copy_safety_on_get(self):
        """Verify that get_progress returns a deep copy to prevent external mutation of the store."""
        task_id = "test-copy-get"
        payload = {"status": "searching", "metadata": {"chapters": [1, 2]}}
        progress_service.set_progress(task_id, payload)

        # Mutate retrieved object
        result = progress_service.get_progress(task_id)
        result["metadata"]["chapters"].append(3)
        result["status"] = "poisoned"

        # Verify store remains unchanged
        verified = progress_service.get_progress(task_id)
        self.assertEqual(verified["status"], "searching")
        self.assertEqual(verified["metadata"]["chapters"], [1, 2])

    def test_deep_copy_safety_on_set(self):
        """Verify that set_progress deep-copies the payload to prevent external mutation of the store."""
        task_id = "test-copy-set"
        payload = {"status": "searching", "metadata": {"chapters": [1, 2]}}

        progress_service.set_progress(task_id, payload)

        # Mutate original input object
        payload["metadata"]["chapters"].append(3)

        # Verify store remains unchanged
        verified = progress_service.get_progress(task_id)
        self.assertEqual(verified["metadata"]["chapters"], [1, 2])

    def test_deep_copy_safety_on_update(self):
        """Verify that update_progress_entry deep-copies input fields to prevent store poisoning."""
        task_id = "test-copy-update"
        progress_service.set_progress(task_id, {"status": "searching"})

        update_fields = {"extra": {"details": "none"}}
        progress_service.update_progress_entry(task_id, **update_fields)

        # Mutate the dictionary that was passed in
        update_fields["extra"]["details"] = "poisoned"

        # Verify store remains unchanged
        verified = progress_service.get_progress(task_id)
        self.assertEqual(verified["extra"]["details"], "none")

    def test_progress_store_debounced_flush_and_terminal_force_flush(self):
        task_id = "task-debounce"
        with patch.object(progress_service, "PROGRESS_STORE_FLUSH_INTERVAL_SECONDS", 60.0):
            progress_service.set_progress(task_id, {"status": "downloading", "percent": 0})

            with open(progress_service.PROGRESS_STORE_FILE, "r", encoding="utf-8") as f:
                first_payload = json.load(f)
            self.assertEqual(first_payload["tasks"][task_id]["status"], "downloading")

            progress_service.update_progress_entry(task_id, percent=25)
            with open(progress_service.PROGRESS_STORE_FILE, "r", encoding="utf-8") as f:
                second_payload = json.load(f)
            # Debounced write: persisted payload should still be pre-update snapshot.
            self.assertEqual(second_payload["tasks"][task_id]["percent"], 0)

            progress_service.update_progress_entry(task_id, status="success", percent=100)
            with open(progress_service.PROGRESS_STORE_FILE, "r", encoding="utf-8") as f:
                final_payload = json.load(f)
            self.assertEqual(final_payload["tasks"][task_id]["status"], "success")
            self.assertEqual(final_payload["tasks"][task_id]["percent"], 100)

if __name__ == "__main__":
    unittest.main()
