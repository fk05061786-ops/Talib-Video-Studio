"""Headless tests for ripple-delete planning and application."""

import unittest
from dataclasses import asdict

from src.core.timeline import TimelineItem
from src.core.timeline_ops import apply_ripple_plan, ripple_delete_plan
from src.core.undo import TimelineState, UndoStack


def clips() -> list:
    return [
        {"id": "a", "start": 0, "duration": 1000, "track_index": 0},
        {"id": "b", "start": 1000, "duration": 1000, "track_index": 0},
        {"id": "c", "start": 2000, "duration": 1000, "track_index": 0},
        {"id": "d", "start": 1000, "duration": 1000, "track_index": 1},
    ]


class TestRippleDeletePlan(unittest.TestCase):
    def test_shifts_only_later_clips_on_same_track(self):
        target, shifts = ripple_delete_plan(clips(), "a")
        self.assertEqual(target["id"], "a")
        self.assertEqual(dict(shifts), {"b": 0, "c": 1000})
        self.assertNotIn("d", dict(shifts))

    def test_apply_plan(self):
        source = clips()
        _target, shifts = ripple_delete_plan(source, "a")
        result = apply_ripple_plan(source, "a", shifts)
        self.assertEqual([clip["id"] for clip in result], ["b", "c", "d"])
        self.assertEqual([clip["start"] for clip in result], [0, 1000, 1000])
        self.assertEqual(source[1]["start"], 1000)
        self.assertEqual(result[1]["start"], 1000)

    def test_missing_target(self):
        target, shifts = ripple_delete_plan(clips(), "missing")
        self.assertIsNone(target)
        self.assertEqual(shifts, [])

    def test_locked_target_is_ignored(self):
        target, shifts = ripple_delete_plan(clips(), "a", locked_ids=("a",))
        self.assertIsNone(target)
        self.assertEqual(shifts, [])

    def test_locked_follower_is_not_shifted(self):
        _target, shifts = ripple_delete_plan(clips(), "a", locked_ids=("c",))
        self.assertEqual(dict(shifts), {"b": 0})

    def test_zero_duration_target(self):
        source = [
            {"id": "a", "start": 0, "duration": 0, "track_index": 0},
            {"id": "b", "start": 1000, "duration": 1000, "track_index": 0},
        ]
        target, shifts = ripple_delete_plan(source, "a")
        self.assertIsNotNone(target)
        self.assertEqual(shifts, [])

    def test_dataclass_clips_are_supported(self):
        source = [
            TimelineItem("a", "c1", "a", 0, 1000, 0),
            TimelineItem("b", "c2", "b", 1000, 1000, 0),
        ]
        target, shifts = ripple_delete_plan(source, "a")
        self.assertEqual(target.id, "a")
        result = apply_ripple_plan(source, "a", shifts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].start_ms, 0)
        self.assertEqual(result[0].name, "b")


class TestRippleDeleteHistory(unittest.TestCase):
    def test_state_before_and_after_are_restorable(self):
        source = clips()
        before = TimelineState(clips=[dict(clip) for clip in source])
        _target, shifts = ripple_delete_plan(source, "a")
        after = TimelineState(clips=apply_ripple_plan(source, "a", shifts))

        stack = UndoStack()
        self.assertTrue(stack.push("Ripple delete", before, after))
        apply = lambda state: [dict(clip) for clip in state.clips]
        self.assertEqual(apply(stack.undo().before), before.clips)
        self.assertEqual(apply(stack.redo().after), after.clips)

    def test_asdict_compatible_clip_fields(self):
        item = TimelineItem("a", "c1", "a", 0, 1000, 0)
        data = asdict(item)
        _target, shifts = ripple_delete_plan([data], "a")
        self.assertEqual(shifts, [])
        self.assertEqual(data["start_ms"], 0)


if __name__ == "__main__":
    unittest.main()
