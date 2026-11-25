"""Headless unit tests for :class:`KeyframeTrack` and evaluation logic."""

import unittest
from src.core.keyframes import KeyframeTrack

class TestKeyframes(unittest.TestCase):
    def setUp(self):
        self.track = KeyframeTrack(name="opacity", default_value=1.0)

    def test_empty_returns_default(self):
        self.assertEqual(self.track.evaluate(1000), 1.0)

    def test_single_keyframe(self):
        self.track.add_keyframe(1000, 0.5)
        self.assertEqual(self.track.evaluate(500), 0.5)
        self.assertEqual(self.track.evaluate(1000), 0.5)
        self.assertEqual(self.track.evaluate(2000), 0.5)

    def test_linear_interpolation(self):
        self.track.add_keyframe(0, 0.0)
        self.track.add_keyframe(1000, 1.0)
        self.assertEqual(self.track.evaluate(500), 0.5)
        self.assertEqual(self.track.evaluate(250), 0.25)

    def test_hold_interpolation(self):
        self.track.add_keyframe(0, 0.0, interpolation="hold")
        self.track.add_keyframe(1000, 1.0)
        self.assertEqual(self.track.evaluate(500), 0.0) # Holds the first value

    def test_clamping(self):
        self.track.add_keyframe(1000, 0.0)
        self.track.add_keyframe(2000, 1.0)
        self.assertEqual(self.track.evaluate(500), 0.0)
        self.assertEqual(self.track.evaluate(2500), 1.0)

    def test_sorting(self):
        self.track.add_keyframe(2000, 1.0)
        self.track.add_keyframe(0, 0.0)
        self.assertEqual(self.track.keyframes[0].time_ms, 0)
        self.assertEqual(self.track.keyframes[1].time_ms, 2000)

    def test_remove_keyframe(self):
        self.track.add_keyframe(1000, 0.5)
        self.assertTrue(self.track.remove_keyframe_at(1000))
        self.assertEqual(self.track.evaluate(1000), 1.0)

if __name__ == "__main__":
    unittest.main()
