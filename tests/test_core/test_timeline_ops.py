"""Headless tests for timeline edit geometry and core overlap rules."""

import unittest

from src.core.timeline import TimelineManager
from src.core.timeline_ops import (
    clamp,
    clip_edges,
    ms_from_x,
    overlapping_clip,
    razor_segments,
    resolve_move,
    resolve_trim,
    ripple_shift,
    snap_position,
    track_from_y,
    trim_bounds,
)


class TestTimelineGeometry(unittest.TestCase):
    def test_clamp_and_coordinates(self):
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)
        self.assertEqual(ms_from_x(500, 0.1), 5000)
        self.assertEqual(ms_from_x(10, 0), 0)
        self.assertEqual(track_from_y(5, 4), 0)
        self.assertEqual(track_from_y(85, 4), 1)
        self.assertEqual(track_from_y(9999, 4), 3)

    def test_snap_position(self):
        self.assertEqual(snap_position(103, [0, 100, 200], 10), 100)
        self.assertEqual(snap_position(105, [0, 200], 10), 105)
        self.assertEqual(snap_position(50, [0, 100], 0), 50)

    def test_clip_edges_and_overlap(self):
        clips = [
            {"id": "a", "start": 0, "duration": 1000, "track_index": 0},
            {"id": "b", "start": 2000, "duration": 1000, "track_index": 0},
        ]
        self.assertEqual(clip_edges(clips), [0, 1000, 2000, 3000])
        self.assertEqual(overlapping_clip(clips, 1500, 2500, track_index=0), "b")
        self.assertIsNone(overlapping_clip(clips, 1000, 2000, track_index=0))
        self.assertIsNone(overlapping_clip(clips, 2000, 3000, ignore_id="b", track_index=0))

    def test_resolve_move(self):
        clips = [{"id": "a", "start": 2000, "duration": 1000, "track_index": 0}]
        self.assertEqual(
            resolve_move(1000, 1000, 0, clips, [1000], 50), 1000
        )
        self.assertIsNone(
            resolve_move(1500, 1000, 0, clips, [1500], 50)
        )
        self.assertEqual(
            resolve_move(1500, 1000, 1, clips, [], 0), 1500
        )

    def test_trim_bounds(self):
        self.assertEqual(trim_bounds(1000, 2000, "start", 500), (1500, 1500))
        self.assertEqual(trim_bounds(1000, 2000, "end", -500), (1000, 1500))
        self.assertEqual(trim_bounds(0, 100, "start", -500), (0, 100))

    def test_resolve_trim_rejects_overlap(self):
        clips = [{"id": "b", "start": 3000, "duration": 1000, "track_index": 0}]
        self.assertIsNone(
            resolve_trim(0, 1000, "end", 3000, 0, clips, [], 0, ignore_id="a")
        )
        self.assertEqual(
            resolve_trim(0, 1000, "end", 1000, 0, clips, [], 0, ignore_id="a"),
            (0, 2000),
        )

    def test_ripple_shift(self):
        clips = [
            {"id": "a", "start": 0, "duration": 1000, "track_index": 0},
            {"id": "b", "start": 1000, "duration": 1000, "track_index": 0},
            {"id": "c", "start": 2000, "duration": 1000, "track_index": 0},
        ]
        self.assertEqual(
            ripple_shift(clips, 1000, 500, ("a",)),
            [("b", 1500), ("c", 2500)],
        )
        self.assertEqual(ripple_shift(clips, 1000, 0), [])

    def test_razor_segments(self):
        segments = razor_segments(0, 5000, 2000, 0, 5000)
        self.assertEqual(
            segments, [(0, 2000, 0, 2000), (2000, 3000, 2000, 5000)]
        )
        self.assertEqual(razor_segments(0, 5000, 0), [])
        self.assertEqual(razor_segments(0, 5000, 5000), [])


class TestCoreOverlapRules(unittest.TestCase):
    def setUp(self):
        self.manager = TimelineManager()

    def test_overlapping_add_rejected(self):
        self.assertIsNotNone(self.manager.add_clip_to_track("c1", "a", 0, 0, 5000))
        self.assertIsNone(self.manager.add_clip_to_track("c2", "b", 0, 2000, 5000))
        self.assertEqual(len(self.manager.tracks[0].items), 1)

    def test_overlap_allowed_when_requested(self):
        manager = TimelineManager(allow_overlap=True)
        manager.add_clip_to_track("c1", "a", 0, 0, 5000)
        self.assertIsNotNone(manager.add_clip_to_track("c2", "b", 0, 2000, 5000))

    def test_move_into_occupied_track_rejected(self):
        first = self.manager.add_clip_to_track("c1", "a", 0, 0, 5000)
        self.manager.add_clip_to_track("c2", "b", 1, 1000, 2000)
        self.assertFalse(self.manager.move_item(first.id, 1, 1500))
        self.assertTrue(self.manager.move_item(first.id, 1, 4000))

    def test_trim_into_neighbour_rejected(self):
        first = self.manager.add_clip_to_track("c1", "a", 0, 0, 1000)
        self.manager.add_clip_to_track("c2", "b", 0, 3000, 1000)
        self.assertFalse(self.manager.trim_item(first.id, 0, 3500))
        self.assertTrue(self.manager.trim_item(first.id, 0, 2000))

    def test_locked_tracks_still_block(self):
        self.manager.tracks[0].is_locked = True
        self.assertIsNone(self.manager.add_clip_to_track("c1", "a", 0, 0, 1000))


if __name__ == "__main__":
    unittest.main()
