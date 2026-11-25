"""Headless tests for frame-accurate timecode and stepping logic.

These tests import only Qt-free helpers so they run without PySide6 or a
display.
"""

import unittest

from src.core.timecode import (
    format_timecode,
    frames_to_ms,
    ms_to_frames,
    step_frames,
    step_position,
)


class TestTimecode(unittest.TestCase):
    def test_ms_to_frames(self):
        self.assertEqual(ms_to_frames(0, 30), 0)
        self.assertEqual(ms_to_frames(1000, 30), 30)
        self.assertEqual(ms_to_frames(500, 30), 15)

    def test_frames_to_ms(self):
        self.assertEqual(frames_to_ms(0, 30), 0)
        self.assertEqual(frames_to_ms(30, 30), 1000)
        self.assertEqual(frames_to_ms(15, 30), 500)

    def test_round_trip(self):
        for ms in (0, 33, 250, 1000, 3333, 59999):
            frame = ms_to_frames(ms, 30)
            self.assertLessEqual(abs(frames_to_ms(frame, 30) - ms), 17)

    def test_format_timecode_zero(self):
        self.assertEqual(format_timecode(0, 30), "00:00:00:00")

    def test_format_timecode_frames(self):
        self.assertEqual(format_timecode(500, 30), "00:00:00:15")
        self.assertEqual(format_timecode(1000, 30), "00:00:01:00")
        self.assertEqual(format_timecode(3661010, 30), "01:01:01:00")

    def test_format_timecode_non_integer_fps(self):
        self.assertEqual(format_timecode(1001, 29.97), "00:00:01:00")

    def test_step_frames(self):
        self.assertEqual(step_frames(1000, 1, 30), 1033)
        self.assertEqual(step_frames(1000, -1, 30), 967)

    def test_step_position_clamps_low(self):
        self.assertEqual(step_position(0, -1, 30), 0)
        self.assertEqual(step_position(10, -5, 30), 0)

    def test_step_position_clamps_high(self):
        self.assertEqual(step_position(1000, 1, 30, duration_ms=1000), 1000)
        self.assertEqual(step_position(900, 10, 30, duration_ms=1000), 1000)

    def test_step_position_unbounded(self):
        self.assertEqual(step_position(1000, 1, 30), 1033)

    def test_zero_fps_safe(self):
        self.assertEqual(frames_to_ms(10, 0), 0)
        self.assertEqual(format_timecode(1000, 0), "00:00:00:00")


if __name__ == "__main__":
    unittest.main()
