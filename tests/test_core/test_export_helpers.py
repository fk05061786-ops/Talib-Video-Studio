"""Headless unit tests for export_helpers module."""

import unittest
from src.core.export_helpers import (
    build_srt_document,
    escape_ffmetadata,
    build_ffmetadata_chapters,
    sanitize_output_stem,
)
from src.core.subtitles import SubtitleCue
from src.core.markers import Marker


class TestExportHelpers(unittest.TestCase):
    def test_build_srt_document(self):
        cues = [
            SubtitleCue(start_ms=2000, end_ms=4000, text="Second line", speaker="Bob"),
            SubtitleCue(start_ms=0, end_ms=1500, text="First line"),
        ]
        srt = build_srt_document(cues)
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,500\n"
            "First line\n\n"
            "2\n"
            "00:00:02,000 --> 00:00:04,000\n"
            "Bob: Second line\n"
        )
        self.assertEqual(srt, expected)

    def test_build_srt_document_empty(self):
        self.assertEqual(build_srt_document([]), "")

    def test_escape_ffmetadata(self):
        self.assertEqual(escape_ffmetadata("a=b;c#d\ne\\f"), "a\\=b\\;c\\#d\\\ne\\\\f")

    def test_build_ffmetadata_chapters(self):
        markers = [
            Marker(time_ms=0, label="Intro", duration_ms=5000),
            Marker(time_ms=5000, label="Pointless", duration_ms=0),  # Should be skipped
            Marker(time_ms=5000, label="Chapter = 1", duration_ms=10000),
        ]
        metadata = build_ffmetadata_chapters(markers)
        expected = (
            ";FFMETADATA1\n"
            "[CHAPTER]\n"
            "TIMEBASE=1/1000\n"
            "START=0\n"
            "END=5000\n"
            "title=Intro\n"
            "[CHAPTER]\n"
            "TIMEBASE=1/1000\n"
            "START=5000\n"
            "END=15000\n"
            "title=Chapter \\= 1\n"
        )
        self.assertEqual(metadata, expected)

    def test_sanitize_output_stem(self):
        self.assertEqual(sanitize_output_stem(" My  Awesome Video!! "), "My_Awesome_Video")
        self.assertEqual(sanitize_output_stem("file/name:test?.mp4"), "file_name_test_.mp4")
        self.assertEqual(sanitize_output_stem("  ...  "), "export")
        self.assertEqual(sanitize_output_stem(""), "export")


if __name__ == "__main__":
    unittest.main()
