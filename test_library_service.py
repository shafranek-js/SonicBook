import unittest
import os
import tempfile
import json
import subprocess
from unittest.mock import patch, MagicMock

from library_service import load_sidecar_metadata_from_path, get_file_duration_seconds

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

    @patch('os.path.exists')
    def test_get_file_duration_seconds_not_exists(self, mock_exists):
        mock_exists.return_value = False
        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

    @patch('os.path.exists')
    def test_get_file_duration_seconds_zip(self, mock_exists):
        mock_exists.return_value = True
        result = get_file_duration_seconds("fake.zip")
        self.assertIsNone(result)

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_get_file_duration_seconds_success(self, mock_run, mock_exists):
        mock_exists.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "123.456\n"
        mock_run.return_value = mock_result

        result = get_file_duration_seconds("fake.mp3")
        self.assertEqual(result, 123.46)

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_get_file_duration_seconds_nonzero_returncode(self, mock_run, mock_exists):
        mock_exists.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_get_file_duration_seconds_invalid_float(self, mock_run, mock_exists):
        mock_exists.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid\n"
        mock_run.return_value = mock_result

        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_get_file_duration_seconds_exception(self, mock_run, mock_exists):
        mock_exists.return_value = True

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=12)

        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

    @patch('os.path.exists')
    @patch('subprocess.run')
    def test_get_file_duration_seconds_zero_or_negative(self, mock_run, mock_exists):
        mock_exists.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0\n"
        mock_run.return_value = mock_result

        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

        mock_result.stdout = "-10\n"
        result = get_file_duration_seconds("fake.mp3")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
