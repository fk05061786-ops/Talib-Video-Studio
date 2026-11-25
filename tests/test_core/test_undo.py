"""Headless tests for the Qt-free undo/redo history and state restoration."""

import unittest

from src.core.timeline import TimelineManager
from src.core.undo import (
    TimelineState,
    UndoStack,
    apply_state_to_manager,
    state_from_manager,
)


def clip_state(start: int, duration: int = 1000, item_id: str = "a") -> TimelineState:
    return TimelineState(
        clips=[
            {
                "id": item_id,
                "clip_id": "c1",
                "name": "clip",
                "start": start,
                "duration": duration,
                "track_index": 0,
            }
        ]
    )


class TestUndoStack(unittest.TestCase):
    def test_push_undo_redo(self):
        stack = UndoStack()
        before, after = clip_state(0), clip_state(500)
        self.assertTrue(stack.push("Move clip", before, after))
        self.assertTrue(stack.can_undo)
        self.assertFalse(stack.can_redo)
        self.assertEqual(stack.undo_label, "Move clip")

        command = stack.undo()
        self.assertEqual(command.before, before)
        self.assertEqual(command.after, after)
        self.assertFalse(stack.can_undo)
        self.assertTrue(stack.can_redo)
        self.assertEqual(stack.redo_label, "Move clip")

        command = stack.redo()
        self.assertEqual(command.after, after)
        self.assertFalse(stack.can_redo)
        self.assertTrue(stack.can_undo)

    def test_identical_states_are_ignored(self):
        stack = UndoStack()
        self.assertFalse(stack.push("No-op", clip_state(0), clip_state(0)))
        self.assertEqual(stack.count, 0)
        self.assertFalse(stack.can_undo)

    def test_limit_drops_oldest_entry(self):
        stack = UndoStack(limit=2)
        stack.push("one", clip_state(0), clip_state(1))
        stack.push("two", clip_state(1), clip_state(2))
        stack.push("three", clip_state(2), clip_state(3))
        self.assertEqual(stack.count, 2)
        self.assertEqual(stack.undo_label, "three")

    def test_new_edit_clears_redo(self):
        stack = UndoStack()
        stack.push("one", clip_state(0), clip_state(1))
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.push("two", clip_state(5), clip_state(6))
        self.assertFalse(stack.can_redo)

    def test_clear(self):
        stack = UndoStack()
        stack.push("one", clip_state(0), clip_state(1))
        stack.clear()
        self.assertIsNone(stack.undo())
        self.assertIsNone(stack.redo())
        self.assertFalse(stack.can_undo)

    def test_snapshot_copy_is_isolated(self):
        state = clip_state(0)
        saved = state.copy()
        state.clips[0]["start"] = 999
        self.assertEqual(saved.clips[0]["start"], 0)

    def test_boundary_returns_none(self):
        stack = UndoStack()
        self.assertIsNone(stack.undo())
        self.assertIsNone(stack.redo())


class TestTimelineStateRestoration(unittest.TestCase):
    def setUp(self):
        self.manager = TimelineManager()

    def test_manager_round_trip_preserves_effects_and_flags(self):
        item = self.manager.add_clip_to_track("c1", "clip", 0, 0, 1000)
        item.brightness = 0.4
        item.text_overlay = "Hello"
        self.manager.tracks[0].is_muted = True
        self.manager.tracks[1].is_locked = True

        snapshot = state_from_manager(self.manager)
        self.manager.tracks[0].items.clear()
        self.manager.tracks[0].is_muted = False
        self.manager.tracks[1].is_locked = False

        apply_state_to_manager(snapshot, self.manager)
        self.assertEqual(state_from_manager(self.manager), snapshot)
        self.assertEqual(self.manager.tracks[0].items[0].brightness, 0.4)
        self.assertEqual(self.manager.tracks[0].items[0].text_overlay, "Hello")
        self.assertTrue(self.manager.tracks[0].is_muted)
        self.assertTrue(self.manager.tracks[1].is_locked)

    def test_full_add_move_trim_split_cycle(self):
        stack = UndoStack()
        initial = state_from_manager(self.manager)

        item = self.manager.add_clip_to_track("c1", "clip", 0, 0, 5000)
        stack.push("Add clip", initial, state_from_manager(self.manager))

        before = state_from_manager(self.manager)
        self.manager.move_item(item.id, 1, 1000)
        stack.push("Move clip", before, state_from_manager(self.manager))

        before = state_from_manager(self.manager)
        self.manager.trim_item(item.id, 1000, 4000)
        stack.push("Trim clip", before, state_from_manager(self.manager))

        before = state_from_manager(self.manager)
        split = self.manager.split_item(item.id, 2000)
        self.assertEqual(len(split), 2)
        final = state_from_manager(self.manager)
        stack.push("Razor clip", before, final)

        while stack.can_undo:
            command = stack.undo()
            apply_state_to_manager(command.before, self.manager)
        self.assertEqual(state_from_manager(self.manager), initial)

        while stack.can_redo:
            command = stack.redo()
            apply_state_to_manager(command.after, self.manager)
        self.assertEqual(state_from_manager(self.manager), final)

    def test_restoring_snapshots_of_transitions_and_track_flags(self):
        start = TimelineState()
        edited = TimelineState(
            transitions=[
                {
                    "kind": "crossfade",
                    "duration_ms": 500,
                    "from_id": "a",
                    "to_id": "b",
                    "track_index": 0,
                }
            ],
            muted_tracks=[1],
            locked_tracks=[0],
        )
        stack = UndoStack()
        stack.push("Add transition", start, edited)
        self.assertEqual(stack.undo().before, start)
        self.assertEqual(stack.redo().after, edited)

    def test_allow_overlap_flag_survives_restore(self):
        manager = TimelineManager(allow_overlap=True)
        manager.add_clip_to_track("c1", "a", 0, 0, 1000)
        snapshot = state_from_manager(manager)
        apply_state_to_manager(snapshot, manager)
        self.assertTrue(manager.allow_overlap)

    def test_ripple_delete_state_round_trip(self):
        first = self.manager.add_clip_to_track("c1", "a", 0, 0, 1000)
        second = self.manager.add_clip_to_track("c2", "b", 0, 1000, 1000)
        initial = state_from_manager(self.manager)

        snap = state_from_manager(self.manager)
        snap.clips = [c for c in snap.clips if c["id"] != first.id]
        for entry in snap.clips:
            if entry["id"] == second.id:
                entry["start"] = 0
        apply_state_to_manager(snap, self.manager)
        self.assertEqual(len(self.manager.tracks[0].items), 1)
        self.assertEqual(self.manager.tracks[0].items[0].start_ms, 0)

        apply_state_to_manager(initial, self.manager)
        self.assertEqual(state_from_manager(self.manager), initial)


if __name__ == "__main__":
    unittest.main()
