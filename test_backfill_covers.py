import sys
from unittest.mock import MagicMock

# Mock dependencies to avoid import errors
sys.modules["httpx"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["scraper"] = MagicMock()
sys.modules["processor"] = MagicMock()
sys.modules["config"] = MagicMock()

import unittest
from backfill_covers import normalize_text

class TestNormalizeText(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")

    def test_basic_normalization(self):
        self.assertEqual(normalize_text("Hello World"), "hello world")
        self.assertEqual(normalize_text("  Mixed CASE  "), "mixed case")

    def test_whitespace_handling(self):
        self.assertEqual(normalize_text("  multiple   spaces  "), "multiple spaces")
        self.assertEqual(normalize_text("\tnew\nline\r"), "new line")

    def test_special_characters(self):
        self.assertEqual(normalize_text("title (2023)!!!"), "title 2023")
        self.assertEqual(normalize_text("author - title"), "author title")
        self.assertEqual(normalize_text("rock & roll"), "rock roll")

    def test_cyrillic_and_yo(self):
        self.assertEqual(normalize_text("Пётр I"), "петр i")
        self.assertEqual(normalize_text("Ёлка"), "елка")
        self.assertEqual(normalize_text("Приключения Электроника"), "приключения электроника")

    def test_unicode_support(self):
        self.assertEqual(normalize_text("Schloß"), "schloß")
        self.assertEqual(normalize_text("Café"), "café")
        self.assertEqual(normalize_text("你好"), "你好")
        self.assertEqual(normalize_text("مرحبا"), "مرحبا")

    def test_numeric_handling(self):
        self.assertEqual(normalize_text("Agent 007"), "agent 007")
        self.assertEqual(normalize_text("123-456"), "123 456")

    def test_strip_punctuation_at_edges(self):
        self.assertEqual(normalize_text("...title..."), "title")
        self.assertEqual(normalize_text("!!!"), "")

if __name__ == "__main__":
    unittest.main()
