"""Headless unit tests for subtitle cue logic."""

import unittest
from src.core.subtitles import SubtitleCue, SubtitleTrack, format_srt_time

class TestSubtitles(unittest.TestCase):
    def test_cue_creation(self):
        cue = SubtitleCue(start_ms=1000, end_ms=2000, text="Hello World")
        self.assertEqual(cue.start_ms, 1000)
        self.assertEqual(cue.end_ms, 2000)
        self.assertEqual(cue.text, "Hello World")

    def test_invalid_cues(self):
        with self.assertRaises(ValueError):
            SubtitleCue(start_ms=-100, end_ms=1000, text="Invalid")
        with self.assertRaises(ValueError):
            SubtitleCue(start_ms=2000, end_ms=1000, text="Invalid")
        with self.assertRaises(ValueError):
            SubtitleCue(start_ms=1000, end_ms=2000, text="  ")

    def test_track_addition_and_overlap(self):
        track = SubtitleTrack()
        cue1 = SubtitleCue(1000, 2000, "First")
        cue2 = SubtitleCue(2000, 3000, "Second")
        track.add_cue(cue1)
        track.add_cue(cue2)
        self.assertEqual(len(track.cues), 2)

        overlapping_cue = SubtitleCue(1500, 2500, "Overlap")
        with self.assertRaises(ValueError):
            track.add_cue(overlapping_cue)

    def test_find_at(self):
        track = SubtitleTrack()
        cue1 = SubtitleCue(1000, 2000, "First")
        track.add_cue(cue1)

        self.assertIsNone(track.find_at(500))
        self.assertEqual(track.find_at(1000), cue1)
        self.assertEqual(track.find_at(1500), cue1)
        self.assertIsNone(track.find_at(2000))  # Range is [start, end)

    def test_srt_time_formatting(self):
        self.assertEqual(format_srt_time(0), "00:00:00,000")
        self.assertEqual(format_srt_time(3661005), "01:01:01,005")

if __name__ == "__main__":
    unittest.main()
