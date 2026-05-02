import json
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import scraper


class TestScraperPreviewCache(unittest.IsolatedAsyncioTestCase):
    async def test_get_book_info_uses_preview_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = os.path.join(tmp, "preview_cache.json")
            url = "https://example.org/book"
            with patch("scraper.PREVIEW_CACHE_FILE", cache_file):
                scraper._preview_cache.clear()
                scraper._preview_cache[url] = {
                    "created_at": time.time(),
                    "result": {
                        "m3u8": "https://cdn.example.org/stream.m3u8",
                        "title": "Cached Book",
                        "chapters": [{"title": "Chapter 1", "start": 0, "end": 120}],
                        "cover": "https://cdn.example.org/cover.jpg",
                    },
                }

                with patch("scraper._parse_text_based", new=AsyncMock()) as mock_text_parse, \
                     patch("scraper._parse_browser_based", new=AsyncMock(return_value="")) as mock_browser_parse:
                    result = await scraper.get_book_info(url)

                self.assertEqual(result[0], "https://cdn.example.org/stream.m3u8")
                self.assertEqual(result[1], "Cached Book")
                mock_text_parse.assert_not_awaited()
                mock_browser_parse.assert_not_awaited()

    def test_preview_cache_persists_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = os.path.join(tmp, "preview_cache.json")
            url = "https://example.org/book-2"

            with patch("scraper.PREVIEW_CACHE_FILE", cache_file):
                scraper._preview_cache.clear()
                scraper._cache_book_info(
                    url,
                    "https://cdn.example.org/book-2.m3u8",
                    "Book 2",
                    [{"title": "One", "start": 0, "end": 60}],
                    None,
                )

                scraper._preview_cache.clear()
                scraper._load_preview_cache_from_disk()
                cached = scraper._get_cached_book_info(url)

            self.assertIsNotNone(cached)
            self.assertEqual(cached[1], "Book 2")

    def test_preview_cache_expired_entry_removed_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = os.path.join(tmp, "preview_cache.json")
            url = "https://example.org/expired-book"
            stale_created_at = time.time() - (scraper.PREVIEW_CACHE_TTL_SECONDS + 30)
            payload = {
                "entries": {
                    url: {
                        "created_at": stale_created_at,
                        "result": {
                            "m3u8": "https://cdn.example.org/expired.m3u8",
                            "title": "Expired",
                            "chapters": [],
                            "cover": None,
                        },
                    }
                }
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            with patch("scraper.PREVIEW_CACHE_FILE", cache_file):
                scraper._preview_cache.clear()
                scraper._load_preview_cache_from_disk()
                cached = scraper._get_cached_book_info(url)

            self.assertIsNone(cached)
            self.assertFalse(os.path.exists(cache_file))


if __name__ == "__main__":
    unittest.main()
