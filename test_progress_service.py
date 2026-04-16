import unittest
from unittest.mock import patch
import time
import progress_service

class TestProgressService(unittest.TestCase):
    def setUp(self):
        progress_service.progress_store.clear()

    def test_create_progress_entry(self):
        url = "http://example.com"
        mode = "download"
        entry = progress_service.create_progress_entry(url, mode)

        self.assertEqual(entry["status"], "searching")
        self.assertEqual(entry["phase"], "searching")
        self.assertEqual(entry["percent"], 0.0)
        self.assertEqual(entry["source_url"], url)
        self.assertEqual(entry["mode"], mode)
        self.assertIn("timestamp", entry)
        self.assertIsInstance(entry["timestamp"], float)

    def test_get_progress_not_found(self):
        result = progress_service.get_progress("non-existent")
        self.assertEqual(result, {"status": "not_found"})

    def test_set_and_get_progress(self):
        task_id = "task-1"
        payload = {"status": "processing", "percent": 50.0}
        progress_service.set_progress(task_id, payload)

        result = progress_service.get_progress(task_id)
        self.assertEqual(result, payload)

    def test_update_progress_entry(self):
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            task_id = "task-1"
            entry = progress_service.create_progress_entry("url")
            old_timestamp = entry["timestamp"]
            progress_service.set_progress(task_id, entry)

            mock_time.return_value = 1001.0
            updated = progress_service.update_progress_entry(task_id, percent=75.0, status="downloading")

            self.assertEqual(updated["percent"], 75.0)
            self.assertEqual(updated["status"], "downloading")
            self.assertEqual(updated["timestamp"], 1001.0)
            self.assertGreater(updated["timestamp"], old_timestamp)

            # Verify it updated in the store
            self.assertEqual(progress_service.get_progress(task_id)["percent"], 75.0)

    def test_update_progress_entry_non_existent(self):
        result = progress_service.update_progress_entry("non-existent", percent=10.0)
        self.assertIsNone(result)

    def test_cleanup_expired_progress(self):
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            # 1. Active task (should not be deleted)
            progress_service.set_progress("active", {"status": "downloading", "timestamp": 900.0})

            # 2. Terminal task, not expired (should not be deleted)
            progress_service.set_progress("recent_success", {"status": "success", "timestamp": 950.0})

            # 3. Terminal task, expired (SHOULD be deleted)
            progress_service.set_progress("old_error", {"status": "error", "timestamp": 800.0})

            # Expire seconds = 100. (1000 - 800 = 200 > 100)
            deleted = progress_service.cleanup_expired_progress(100)

            self.assertIn("old_error", deleted)
            self.assertNotIn("active", deleted)
            self.assertNotIn("recent_success", deleted)
            self.assertNotIn("old_error", progress_service.progress_store)
            self.assertIn("active", progress_service.progress_store)
            self.assertIn("recent_success", progress_service.progress_store)

    def test_find_active_task_by_source(self):
        url = "http://test.com"

        # 1. No task for URL
        self.assertIsNone(progress_service.find_active_task_by_source(url))

        # 2. Terminal task for URL
        progress_service.set_progress("task-1", {"source_url": url, "status": "success"})
        self.assertIsNone(progress_service.find_active_task_by_source(url))

        # 3. Active task for URL
        progress_service.set_progress("task-2", {"source_url": url, "status": "downloading"})
        tid, data = progress_service.find_active_task_by_source(url)
        self.assertEqual(tid, "task-2")
        self.assertEqual(data["status"], "downloading")

        # 4. Another URL
        self.assertIsNone(progress_service.find_active_task_by_source("http://other.com"))

    def test_find_active_task_by_source_empty_url(self):
        self.assertIsNone(progress_service.find_active_task_by_source(""))

    def test_get_progress_cache_poisoning(self):
        task_id = "test-1"
        payload = {"status": "searching", "percent": 10.0}
        progress_service.set_progress(task_id, payload)

        result = progress_service.get_progress(task_id)
        result["percent"] = 99.0  # Attempt to poison the cache

        cached_result = progress_service.get_progress(task_id)
        self.assertEqual(cached_result["percent"], 10.0, "Cache was poisoned!")

    def test_update_progress_entry_cache_poisoning(self):
        task_id = "test-2"
        payload = {"status": "searching", "percent": 10.0}
        progress_service.set_progress(task_id, payload)

        result = progress_service.update_progress_entry(task_id, percent=20.0)
        self.assertEqual(result["percent"], 20.0)

        result["percent"] = 99.0  # Attempt to poison the cache

        cached_result = progress_service.get_progress(task_id)
        self.assertEqual(cached_result["percent"], 20.0, "Cache was poisoned!")

    def test_find_active_task_by_source_cache_poisoning(self):
        task_id = "test-3"
        url = "http://poison.com"
        payload = {"status": "searching", "percent": 10.0, "source_url": url}
        progress_service.set_progress(task_id, payload)

        tid, data = progress_service.find_active_task_by_source(url)
        data["percent"] = 99.0  # Attempt to poison the cache

        cached_result = progress_service.get_progress(task_id)
        self.assertEqual(cached_result["percent"], 10.0, "Cache was poisoned!")

if __name__ == "__main__":
    unittest.main()
