import sys
import unittest
from unittest.mock import MagicMock

# Mock required modules before importing processor
sys.modules['aiofiles'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['yt_dlp'] = MagicMock()
sys.modules['config'] = MagicMock()

from processor import parse_ffmpeg_out_time

class TestParseFfmpegOutTime(unittest.TestCase):
    def test_valid_time(self):
        self.assertEqual(parse_ffmpeg_out_time("00:00:01"), 1.0)
        self.assertEqual(parse_ffmpeg_out_time("00:01:00"), 60.0)
        self.assertEqual(parse_ffmpeg_out_time("01:00:00"), 3600.0)
        self.assertEqual(parse_ffmpeg_out_time("01:01:01"), 3661.0)
        self.assertEqual(parse_ffmpeg_out_time("00:00:01.5"), 1.5)
        self.assertEqual(parse_ffmpeg_out_time("01:30:15.25"), 5415.25)

    def test_invalid_time(self):
        self.assertEqual(parse_ffmpeg_out_time("invalid"), 0.0)
        self.assertEqual(parse_ffmpeg_out_time(""), 0.0)
        self.assertEqual(parse_ffmpeg_out_time("01:00"), 0.0)
        self.assertEqual(parse_ffmpeg_out_time("01:00:00:00"), 0.0)
        self.assertEqual(parse_ffmpeg_out_time(None), 0.0)
        self.assertEqual(parse_ffmpeg_out_time(123), 0.0)

    def test_edge_cases(self):
        self.assertEqual(parse_ffmpeg_out_time("  01:02:03.4  "), 3723.4) # with spaces
        self.assertEqual(parse_ffmpeg_out_time("0:0:0"), 0.0)
        self.assertEqual(parse_ffmpeg_out_time("100:00:00"), 360000.0) # large hours

    def test_negative_time(self):
        self.assertEqual(parse_ffmpeg_out_time("-01:00:00"), -3600.0)
        self.assertEqual(parse_ffmpeg_out_time("-00:01:00"), -60.0)
        self.assertEqual(parse_ffmpeg_out_time("-00:00:01"), -1.0)
        self.assertEqual(parse_ffmpeg_out_time("-01:02:03.5"), -3723.5)

    def test_malformed_time(self):
        self.assertEqual(parse_ffmpeg_out_time("01:-02:03"), 3483.0) # -2 minutes makes sense mathematically, ffmpeg allows this
        self.assertEqual(parse_ffmpeg_out_time("01:60:00"), 7200.0) # ffmpeg doesn't cap minutes at 59
        self.assertEqual(parse_ffmpeg_out_time("00:00:100"), 100.0)
        self.assertEqual(parse_ffmpeg_out_time("a:b:c"), 0.0)

if __name__ == '__main__':
    unittest.main()
