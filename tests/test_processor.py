import unittest
import sys
from unittest.mock import MagicMock

# Mock missing dependencies to allow importing processor.py
sys.modules["aiofiles"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["yt_dlp"] = MagicMock()
sys.modules["PIL"] = MagicMock()

from processor import sanitize_filename

class TestSanitizeFilename(unittest.TestCase):
    def test_basic_alphanumeric(self):
        self.assertEqual(sanitize_filename("testfile123"), "testfile123")
        self.assertEqual(sanitize_filename("Test File 123"), "Test File 123")

    def test_problematic_characters(self):
        # Commas should be removed
        self.assertEqual(sanitize_filename("file,with,commas"), "filewithcommas")
        # Problematic shell/ffmpeg chars like :;<>| should be removed
        self.assertEqual(sanitize_filename("file:with;others<|>"), "filewithothers")
        # But valid_chars should be kept: -_.()
        self.assertEqual(sanitize_filename("file-with.allowed(chars)_"), "file-with.allowed(chars)_")

    def test_whitespace_handling(self):
        # Multiple spaces should be collapsed
        self.assertEqual(sanitize_filename("file   with  spaces"), "file with spaces")
        # Leading/trailing spaces should be stripped
        self.assertEqual(sanitize_filename("  leading and trailing  "), "leading and trailing")

    def test_cyrillic_characters(self):
        # Cyrillic characters should be preserved
        self.assertEqual(sanitize_filename("привет мир"), "привет мир")
        self.assertEqual(sanitize_filename("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"), "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
        self.assertEqual(sanitize_filename("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"), "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")

    def test_leading_trailing_periods_and_spaces(self):
        # Leading/trailing periods and spaces should be stripped
        self.assertEqual(sanitize_filename(".file."), "file")
        self.assertEqual(sanitize_filename("  .file.  "), "file")
        self.assertEqual(sanitize_filename("...file..."), "file")
        self.assertEqual(sanitize_filename(".. . file . .. "), "file")

    def test_length_limit(self):
        # Should truncate to 100 characters
        long_name = "a" * 150
        sanitized = sanitize_filename(long_name)
        self.assertEqual(len(sanitized), 100)
        self.assertEqual(sanitized, "a" * 100)

    def test_mixed_case(self):
        # ! @ # $ % ^ & * + [ ] { } are NOT in valid_chars
        input_str = "  Some.File, With! @#$%^&*()_+ [Special] {Chars} . "
        # Characters that remain: S o m e . F i l e W i t h ( ) _ S p e c i a l C h a r s
        # Whitespace is collapsed and stripped.
        expected = "Some.File With ()_ Special Chars"
        self.assertEqual(sanitize_filename(input_str), expected)

if __name__ == '__main__':
    unittest.main()
