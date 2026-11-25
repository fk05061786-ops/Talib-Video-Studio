"""Headless tests for effect-registry startup and cross-module integration."""

import tempfile
import unittest
from pathlib import Path

from src.app.startup import init_effect_registry
from src.core.integration import (
    active_values_at,
    integration_status,
    keyframes_from_data,
    keyframes_to_data,
    markers_from_data,
    subtitles_from_data,
    timeline_extent,
    viewport_for_clips,
)


class TestEffectRegistryStartup(unittest.TestCase):
    def test_builtin_registry(self):
        registry = init_effect_registry()
        for name in ("brightness", "contrast", "gain", "crossfade", "title"):
            self.assertTrue(registry.has(name), name)
        self.assertFalse(registry.validate_all().get("brightness"))

    def test_missing_optional_directory_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = init_effect_registry(extra_dir=Path(directory) / "absent")
            self.assertTrue(registry.has("brightness"))

    def test_custom_effects_are_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "custom_fx_plugin.py"
            plugin.write_text(
                "from src.core.effects_registry import EffectMetadata, RegisteredEffect\n"
                "def get_registry():\n"
                "    return [RegisteredEffect(\n"
                "        name='custom_fx', cls=object,\n"
                "        metadata=EffectMetadata(name='custom_fx', category='video'),\n"
                "    )]\n",
                encoding="utf-8",
            )
            registry = init_effect_registry(extra_dir=directory)
            self.assertTrue(registry.has("custom_fx"))
            self.assertTrue(registry.has("brightness"))

    def test_broken_custom_module_does_not_stop_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken_plugin.py").write_text(
                "raise RuntimeError('bad plugin')\n", encoding="utf-8"
            )
            registry = init_effect_registry(extra_dir=directory)
            self.assertTrue(registry.has("brightness"))

    def test_config_directory_key(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = init_effect_registry({"EFFECTS_DIR": directory})
            self.assertTrue(registry.has("gain"))


class TestIntegrationHelpers(unittest.TestCase):
    def setUp(self):
        self.clips = [
            {"id": "a", "start": 0, "duration": 1000, "track_index": 0},
            {"id": "b", "start": 2000, "duration": 3000, "track_index": 0},
        ]

    def test_timeline_extent(self):
        self.assertEqual(timeline_extent(self.clips), (0, 5000))
        self.assertEqual(timeline_extent([]), (0, 0))

    def test_viewport_for_clips(self):
        state = viewport_for_clips(self.clips, 1000, padding_ms=0)
        self.assertGreater(state.zoom_level, 0)
        self.assertEqual(state.view_width, 1000)
        self.assertEqual(viewport_for_clips([], 800).zoom_level, 0.8)

    def test_marker_parsing_skips_bad_entries(self):
        track = markers_from_data(
            [
                {"time_ms": 1000, "label": "Intro"},
                {"time_ms": -1, "label": "bad"},
                {"label": "missing time"},
            ]
        )
        self.assertEqual(len(track.markers), 1)
        self.assertEqual(track.find_next(500).label, "Intro")

    def test_subtitle_parsing_skips_bad_and_overlapping(self):
        track = subtitles_from_data(
            [
                {"start_ms": 1000, "end_ms": 2000, "text": "Hello"},
                {"start_ms": 1500, "end_ms": 2500, "text": "Overlap"},
                {"start_ms": -5, "end_ms": 10, "text": "Bad"},
            ]
        )
        self.assertEqual(len(track.cues), 1)
        self.assertEqual(track.find_at(1500).text, "Hello")

    def test_keyframe_round_trip(self):
        tracks = keyframes_from_data(
            {"brightness": [{"time_ms": 0, "value": 0}, {"time_ms": 1000, "value": 1}]}
        )
        data = keyframes_to_data(tracks)
        self.assertEqual(len(data["brightness"]), 2)
        self.assertEqual(active_values_at(tracks, 500)["brightness"], 0.5)

    def test_integration_status(self):
        markers = markers_from_data([{"time_ms": 2000, "label": "Chapter"}])
        subtitles = subtitles_from_data(
            [{"start_ms": 0, "end_ms": 3000, "text": "Caption"}]
        )
        tracks = keyframes_from_data(
            {"contrast": [{"time_ms": 0, "value": 1}, {"time_ms": 4000, "value": 2}]}
        )
        status = integration_status(
            self.clips,
            markers=markers,
            subtitles=subtitles,
            keyframes=tracks,
            playhead_ms=2000,
            view_width=1000,
        )
        self.assertEqual(status["timeline_end_ms"], 5000)
        self.assertEqual(status["next_marker_ms"], 2000)
        self.assertEqual(status["subtitle_text"], "Caption")
        self.assertEqual(status["keyframe_values"]["contrast"], 1.5)

    def test_status_without_annotations(self):
        status = integration_status([], playhead_ms=-5)
        self.assertEqual(status["playhead_ms"], 0)
        self.assertEqual(status["subtitle_text"], "")
        self.assertEqual(status["keyframe_values"], {})


if __name__ == "__main__":
    unittest.main()
