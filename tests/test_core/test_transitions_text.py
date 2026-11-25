"""Headless tests for transition and text-overlay helpers."""

import unittest

from src.core.text_styles import (
    TEXT_PRESETS,
    build_drawtext,
    escape_drawtext,
    style_from_dict,
    style_from_preset,
)
from src.core.transitions import make_transition, overlap_ms, xfade_offsets


class TestTransitions(unittest.TestCase):
    def test_overlap(self):
        first = {"start": 0, "duration": 5000}
        second = {"start": 4000, "duration": 5000}
        third = {"start": 6000, "duration": 1000}
        self.assertEqual(overlap_ms(first, second), 1000)
        self.assertEqual(overlap_ms(first, third), 0)

    def test_make_transition_caps_overlap(self):
        first = {"id": "a", "start": 0, "duration": 5000, "track_index": 0}
        second = {"id": "b", "start": 4000, "duration": 5000, "track_index": 0}
        transition = make_transition(first, second, 500)
        self.assertIsNotNone(transition)
        self.assertEqual(transition.duration_ms, 500)
        self.assertEqual(transition.from_id, "a")
        self.assertEqual((transition.to_id, transition.track_index), ("b", 0))
        self.assertEqual(
            make_transition(first, second, 5000).duration_ms, 1000
        )

    def test_invalid_transitions(self):
        first = {"id": "a", "start": 0, "duration": 1000}
        second = {"id": "b", "start": 5000, "duration": 1000}
        self.assertIsNone(make_transition(first, second, 500))
        self.assertIsNone(make_transition(first, {"id": "b", "start": 0, "duration": 1000}, 500, "wipe"))

    def test_xfade_offsets(self):
        self.assertEqual(xfade_offsets([5000, 5000, 5000], [500, 500]), [4.5, 9.0])
        self.assertEqual(xfade_offsets([5000], []), [])
        self.assertEqual(xfade_offsets([5000, 5000], [500]), [4.5])
        self.assertEqual(xfade_offsets([5000, 5000], [500, 500]), [])


class TestTextStyles(unittest.TestCase):
    def test_presets(self):
        self.assertIn("lower_third", TEXT_PRESETS)
        style = style_from_preset("lower_third", "Hello")
        self.assertEqual(style.text, "Hello")
        self.assertEqual(style.position, "bottom-left")
        self.assertTrue(style.box)

    def test_escape_drawtext(self):
        self.assertEqual(escape_drawtext("a:b'c,d\\e"), "a\\:b\\'c\\,d\\\\e")

    def test_build_drawtext(self):
        filter_text = build_drawtext(style_from_preset("title", "Hi"))
        self.assertTrue(filter_text.startswith("drawtext="))
        self.assertIn("fontsize=72", filter_text)
        self.assertIn("fontweight=bold", filter_text)
        self.assertIn("borderw=2", filter_text)
        self.assertIn("x=(w-text_w)/2", filter_text)

    def test_drawtext_position_and_enable(self):
        style = style_from_preset("centered", "Later", position="top", start_sec=1, end_sec=3)
        filter_text = build_drawtext(style)
        self.assertIn("y=20", filter_text)
        self.assertIn("enable='between(t,1.000,3.000)'", filter_text)

        no_window = build_drawtext(
            style_from_preset("centered", "Now", start_sec=2, end_sec=2)
        )
        self.assertNotIn("enable=", no_window)

    def test_style_from_dict_ignores_unknown_keys(self):
        style = style_from_dict({"text": "x", "position": "bottom", "unknown": 1})
        self.assertEqual(style.text, "x")
        self.assertEqual(style.position, "bottom")


if __name__ == "__main__":
    unittest.main()
