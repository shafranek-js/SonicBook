import unittest
import os
import tempfile
import json
from unittest.mock import patch

from library_service import (
    load_sidecar_metadata_from_path,
    _sidecar_json_path,
    load_sidecar_metadata,
)

class TestLibraryService(unittest.TestCase):
    @patch("library_service.os.path.exists")
    def test_load_sidecar_metadata_from_path_missing_file(self, mock_exists):
        # Mock os.path.exists to return False
        mock_exists.return_value = False
        result = load_sidecar_metadata_from_path("/path/to/non/existent/file.json")
        self.assertIsNone(result)
        mock_exists.assert_called_once_with("/path/to/non/existent/file.json")

    def test_load_sidecar_metadata_from_path_valid_json(self):
        # Create a temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump({"key": "value"}, f)
            temp_path = f.name

        try:
            result = load_sidecar_metadata_from_path(temp_path)
            self.assertEqual(result, {"key": "value"})
        finally:
            os.remove(temp_path)

    def test_load_sidecar_metadata_from_path_invalid_json(self):
        # Create a temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write("invalid json {")
            temp_path = f.name

        try:
            result = load_sidecar_metadata_from_path(temp_path)
            self.assertIsNone(result)
        finally:
            os.remove(temp_path)

    def test_sidecar_json_path(self):
        self.assertEqual(_sidecar_json_path("/a/b/c.mp3"), "/a/b/c.json")
        self.assertEqual(_sidecar_json_path("/some/long/path/file.name.m4b"), "/some/long/path/file.name.json")
        self.assertEqual(_sidecar_json_path("local.zip"), "local.json")

    @patch("library_service.load_sidecar_metadata_from_path")
    def test_load_sidecar_metadata(self, mock_load):
        mock_load.return_value = {"mock": "data"}
        result = load_sidecar_metadata("/path/to/book.mp3")
        mock_load.assert_called_once_with("/path/to/book.json")
        self.assertEqual(result, {"mock": "data"})

if __name__ == '__main__':
    unittest.main()
