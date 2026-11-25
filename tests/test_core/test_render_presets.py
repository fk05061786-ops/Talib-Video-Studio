"""Headless tests for render presets."""

import unittest
from src.core.render_presets import RenderPreset, get_preset, list_presets, PRESETS

class TestRenderPresets(unittest.TestCase):
    def test_preset_validation(self):
        # Valid
        p = RenderPreset("Valid", 1920, 1080, 30.0)
        self.assertEqual(p.width, 1920)

        # Invalid Width (Odd)
        with self.assertRaises(ValueError):
            RenderPreset("Odd", 1921, 1080, 30.0)

        # Invalid Height (Odd)
        with self.assertRaises(ValueError):
            RenderPreset("Odd", 1920, 1081, 30.0)

        # Invalid FPS
        with self.assertRaises(ValueError):
            RenderPreset("Zero FPS", 1920, 1080, 0.0)

    def test_get_and_list_presets(self):
        self.assertIsNotNone(get_preset("youtube_1080p"))
        self.assertIsNone(get_preset("unknown"))
        presets_dict = list_presets()
        self.assertIn("youtube_1080p", presets_dict)

if __name__ == "__main__":
    unittest.main()
