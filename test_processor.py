import unittest

from processor import parse_ffmpeg_out_time, parse_content_range_header

class TestParseContentRangeHeader(unittest.TestCase):
    def test_valid_range_with_total(self):
        self.assertEqual(
            parse_content_range_header("bytes 0-499/1234"),
            {"start": 0, "end": 499, "total": 1234}
        )
        self.assertEqual(
            parse_content_range_header("BYTES 500-999/1234"),
            {"start": 500, "end": 999, "total": 1234}
        )
        self.assertEqual(
            parse_content_range_header("bytes 1000-1233/1234"),
            {"start": 1000, "end": 1233, "total": 1234}
        )
        self.assertEqual(
            parse_content_range_header("  bytes 0-100/200  "),
            {"start": 0, "end": 100, "total": 200}
        )

    def test_valid_range_with_star(self):
        self.assertEqual(
            parse_content_range_header("bytes 0-499/*"),
            {"start": 0, "end": 499, "total": None}
        )
        self.assertEqual(
            parse_content_range_header("bytes 500-999/*"),
            {"start": 500, "end": 999, "total": None}
        )

    def test_invalid_range(self):
        self.assertIsNone(parse_content_range_header("invalid"))
        self.assertIsNone(parse_content_range_header(""))
        self.assertIsNone(parse_content_range_header(None))
        self.assertIsNone(parse_content_range_header("bytes 0-499"))
        self.assertIsNone(parse_content_range_header("0-499/1234"))

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
