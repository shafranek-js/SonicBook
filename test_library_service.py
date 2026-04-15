import unittest
import os
import tempfile
import json
from unittest.mock import patch

from library_service import load_sidecar_metadata_from_path

class TestLibraryService(unittest.TestCase):
    def test_load_sidecar_metadata_from_path_missing_file(self):
        # Pass a non-existent path
        result = load_sidecar_metadata_from_path("/path/to/non/existent/file.json")
        self.assertIsNone(result)

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

if __name__ == '__main__':
    unittest.main()
