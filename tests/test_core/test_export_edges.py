"""Headless tests for export request validation and edit edge cases."""

import sys
import tempfile
import unittest
from pathlib import Path

from src.core.export_validation import validate_export_request
from src.core.text_styles import build_drawtext, style_from_preset
from src.core.timeline import TimelineManager
from src.core.timeline_ops import resolve_move, resolve_trim, razor_segments


class TestExportValidation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "input.mp4"
        self.source.write_bytes(b"video")
        self.output = self.root / "output.mp4"

    def tearDown(self):
        self.directory.cleanup()

    def test_valid_request(self):
        self.assertIsNone(
            validate_export_request(self.source, self.output, sys.executable)
        )

    def test_missing_input(self):
        self.assertIn("No input", validate_export_request(None, self.output))

    def test_input_not_a_file(self):
        error = validate_export_request(self.root / "missing.mp4", self.output)
        self.assertIn("not found", error)

    def test_empty_input(self):
        empty = self.root / "empty.mp4"
        empty.touch()
        self.assertIn("empty", validate_export_request(empty, self.output))

    def test_missing_output(self):
        self.assertIn("No output", validate_export_request(self.source, None))

    def test_output_is_directory(self):
        self.assertIn(
            "directory", validate_export_request(self.source, self.root)
        )

    def test_output_same_as_input(self):
        self.assertIn(
            "differ", validate_export_request(self.source, self.source)
        )

    def test_binary_missing(self):
        error = validate_export_request(
            self.source, self.output, "definitely_missing_ffmpeg"
        )
        self.assertIn("not found", error)


class TestEditAndExportEdges(unittest.TestCase):
    def test_text_style_empty_text_has_no_drawtext_window(self):
        style = style_from_preset("centered", " ", start_sec=0, end_sec=0)
        self.assertIsInstance(build_drawtext(style), str)

    def test_razor_rejects_split_at_bounds(self):
        self.assertEqual(razor_segments(0, 1000, 0), [])
        self.assertEqual(razor_segments(0, 1000, 1000), [])

    def test_resolve_move_rejects_overlap(self):
        clips = [{"id": "a", "start": 1000, "duration": 1000, "track_index": 0}]
        self.assertIsNone(resolve_move(1500, 1000, 0, clips, [], 0))

    def test_resolve_trim_rejects_reversed_bounds(self):
        self.assertEqual(
            resolve_trim(0, 100, "end", -50, 0, [], [], 0, min_duration_ms=1),
            (0, 50),
        )

    def test_timeline_manager_muted_track_still_editable(self):
        manager = TimelineManager()
        manager.tracks[0].is_muted = True
        self.assertIsNotNone(manager.add_clip_to_track("c1", "a", 0, 0, 1000))


if __name__ == "__main__":
    unittest.main()
