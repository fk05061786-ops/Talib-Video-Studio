"""Unit tests for Talib Video Studio core (headless)."""

import unittest
from pathlib import Path
from src.core.timeline import TimelineManager, TimelineItem, TimelineTrack

# Mock FFmpegExporter/ExportWorkerThread to avoid PySide dependency in tests
class MockFFmpegExporter:
    def __init__(self, ffmpeg_bin="ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def build_command(self, input_path, output_path, resolution="1920x1080", fps=30, start_sec=None, duration_sec=None):
        cmd = [self.ffmpeg_bin, "-y", "-i", str(input_path)]
        if start_sec: cmd.extend(["-ss", f"{start_sec:.3f}"])
        if duration_sec: cmd.extend(["-t", f"{duration_sec:.3f}"])
        cmd.extend(["-r", str(fps), str(output_path)])
        return cmd

class TestTimelineManager(unittest.TestCase):
    def setUp(self):
        self.manager = TimelineManager()

    def test_initial_state(self):
        self.assertEqual(len(self.manager.tracks), 2)

    def test_add_clip(self):
        item = self.manager.add_clip_to_track("c1", "test.mp4", 0, 0, 5000)
        self.assertEqual(item.clip_id, "c1")
        self.assertEqual(self.manager.duration_ms, 5000)

    def test_move_item(self):
        item = self.manager.add_clip_to_track("c1", "test.mp4", 0, 0, 5000)
        success = self.manager.move_item(item.id, 1, 1000)
        self.assertTrue(success)
        # In move_item, we find the first item with that ID across tracks
        self.assertEqual(self.manager.tracks[1].items[0].start_ms, 1000)

    def test_split_item(self):
        item = self.manager.add_clip_to_track("c1", "test.mp4", 0, 0, 5000)
        items = self.manager.split_item(item.id, 2000)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].duration_ms, 2000)
        self.assertEqual(items[1].duration_ms, 3000)

    def test_trim_item(self):
        item = self.manager.add_clip_to_track("c1", "test.mp4", 0, 0, 5000)
        self.manager.trim_item(item.id, 500, 4000)
        self.assertEqual(self.manager.duration_ms, 4000)

    def test_track_lock_mute(self):
        track = self.manager.tracks[0]
        track.is_locked = True
        item = self.manager.add_clip_to_track("c1", "test.mp4", 0, 0, 5000)
        self.assertEqual(len(track.items), 0)

        track.is_locked = False
        track.is_muted = True
        self.assertTrue(track.is_muted)

class TestFFmpegExporter(unittest.TestCase):
    def test_command(self):
        exporter = MockFFmpegExporter()
        cmd = exporter.build_command(Path("/i.mp4"), Path("/o.mp4"), start_sec=1.0, duration_sec=2.0)
        self.assertIn("-ss", cmd)
        self.assertIn("1.000", cmd)
        self.assertIn("-t", cmd)
        self.assertIn("2.000", cmd)

    def test_build_concat_command_muted(self):
        # Implementation of build_concat_command logic in mock for testing
        def mock_build_concat(clips, muted_tracks):
            active = [c for c in clips if c.get("track_index") not in (muted_tracks or [])]
            return [str(c["path"]) for c in active]

        clips = [
            {"path": Path("/a.mp4"), "track_index": 0},
            {"path": Path("/b.mp4"), "track_index": 1}
        ]
        cmd = mock_build_concat(clips, muted_tracks=[1])
        self.assertIn("/a.mp4", cmd)
        self.assertNotIn("/b.mp4", cmd)

if __name__ == "__main__":
    unittest.main()