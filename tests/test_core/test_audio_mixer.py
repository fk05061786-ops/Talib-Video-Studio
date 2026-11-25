"""Headless tests for audio mixer functions."""

import unittest
from src.core.audio_mixer import (
    AudioMixSettings,
    db_to_linear,
    normalize_audio_settings,
    build_audio_filter,
    build_loudness_filter,
)

class TestAudioMixer(unittest.TestCase):
    def test_db_to_linear(self):
        self.assertAlmostEqual(db_to_linear(0), 1.0)
        self.assertAlmostEqual(db_to_linear(-6), 0.501187, places=4)
        self.assertAlmostEqual(db_to_linear(6), 1.995262, places=4)

    def test_normalize_audio_settings(self):
        settings = normalize_audio_settings({"gain_db": 20, "fade_in_ms": -50})
        self.assertEqual(settings.gain_db, 12.0)  # clamped
        self.assertEqual(settings.fade_in_ms, 0)   # clamped

    def test_build_audio_filter(self):
        settings = AudioMixSettings(gain_db=6, fade_in_ms=1000)
        filt = build_audio_filter(settings)
        self.assertIn("volume=", filt)
        self.assertIn("afade=t=in", filt)

    def test_loudness_filter(self):
        self.assertEqual(build_loudness_filter(), "loudnorm=I=-23.0:TP=-1.0:LRA=11")

if __name__ == "__main__":
    unittest.main()
