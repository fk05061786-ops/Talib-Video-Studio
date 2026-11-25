"""Headless unit tests for timeline marker logic."""

import unittest
from src.core.markers import Marker, MarkerTrack

class TestMarkers(unittest.TestCase):
    def test_marker_creation(self):
        marker = Marker(time_ms=5000, label="Intro", color="#ff0000", notes="Scene 1")
        self.assertEqual(marker.time_ms, 5000)
        self.assertEqual(marker.label, "Intro")
        self.assertEqual(marker.duration_ms, 0)
        self.assertEqual(marker.end_ms, 5000)

    def test_invalid_markers(self):
        with self.assertRaises(ValueError):
            Marker(time_ms=-1, label="Bad")
        with self.assertRaises(ValueError):
            Marker(time_ms=1000, label=" ", duration_ms=0)
        with self.assertRaises(ValueError):
            Marker(time_ms=1000, label="Ok", duration_ms=-10)

    def test_track_sorting(self):
        track = MarkerTrack()
        track.add_marker(Marker(1000, "Second"))
        track.add_marker(Marker(0, "First"))
        self.assertEqual(track.markers[0].label, "First")
        self.assertEqual(track.markers[1].label, "Second")

    def test_find_helpers(self):
        track = MarkerTrack()
        m1 = Marker(1000, "M1")
        m2 = Marker(2000, "M2")
        m3 = Marker(3000, "M3")
        for m in [m1, m2, m3]:
            track.add_marker(m)

        self.assertEqual(track.find_nearest(1600), m2)
        self.assertEqual(track.find_nearest(1400), m1)
        self.assertEqual(track.find_previous(2500), m2)
        self.assertEqual(track.find_next(1500), m2)
        self.assertIsNone(track.find_previous(500))
        self.assertIsNone(track.find_next(3500))

    def test_find_active_chapter(self):
        track = MarkerTrack()
        c1 = Marker(1000, "Chapter 1", duration_ms=1000)
        track.add_marker(c1)

        self.assertIsNone(track.find_active_chapter(500))
        self.assertEqual(track.find_active_chapter(1500), c1)
        self.assertIsNone(track.find_active_chapter(2000))

    def test_remove_marker(self):
        track = MarkerTrack()
        track.add_marker(Marker(1000, "Delete Me"))
        self.assertTrue(track.remove_marker_at(1000))
        self.assertEqual(len(track.markers), 0)
        self.assertFalse(track.remove_marker_at(1000))

if __name__ == "__main__":
    unittest.main()
