"""Qt-free undo/redo history for timeline edits.

The stack stores full timeline snapshots rather than inverse operations: every
edit records its ``before`` and ``after`` state, so restoring is deterministic
even for multi-step edits such as ripple delete or razor splits. No Qt imports
here — the same helpers are used by the UI and by headless tests.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.timeline import TimelineItem, TimelineManager, TimelineTrack
from src.core.timeline_ops import _duration, _start

logger = logging.getLogger(__name__)


@dataclass
class TimelineState:
    """A serializable snapshot of everything the timeline panel owns."""

    clips: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    muted_tracks: List[int] = field(default_factory=list)
    locked_tracks: List[int] = field(default_factory=list)

    def copy(self) -> "TimelineState":
        return TimelineState(
            clips=copy.deepcopy(self.clips),
            transitions=copy.deepcopy(self.transitions),
            muted_tracks=list(self.muted_tracks),
            locked_tracks=list(self.locked_tracks),
        )


@dataclass
class UndoCommand:
    """One reversible edit."""

    label: str
    before: TimelineState
    after: TimelineState


class UndoStack:
    """Bounded undo/redo stack with linear history."""

    def __init__(self, limit: int = 100) -> None:
        self.limit = max(1, int(limit))
        self._undo: List[UndoCommand] = []
        self._redo: List[UndoCommand] = []

    def push(
        self, label: str, before: TimelineState, after: TimelineState
    ) -> bool:
        """Record a change; return ``False`` when before/after are identical."""
        if before == after:
            return False
        self._undo.append(UndoCommand(label, before.copy(), after.copy()))
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()
        return True

    def undo(self) -> Optional[UndoCommand]:
        """Return the command to undo, or ``None`` when at the beginning."""
        if not self._undo:
            return None
        command = self._undo.pop()
        self._redo.append(command)
        return command

    def redo(self) -> Optional[UndoCommand]:
        """Return the command to redo, or ``None`` when at the end."""
        if not self._redo:
            return None
        command = self._redo.pop()
        self._undo.append(command)
        return command

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else ""

    @property
    def count(self) -> int:
        return len(self._undo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()


def state_from_manager(manager: TimelineManager) -> TimelineState:
    """Snapshot a :class:`TimelineManager` (clip fields use ``*_ms`` keys)."""
    clips: List[Dict[str, Any]] = []
    for track in manager.tracks:
        for item in track.items:
            data = {
                "id": item.id,
                "clip_id": item.clip_id,
                "name": item.name,
                "start": item.start_ms,
                "duration": item.duration_ms,
                "track_index": item.track_index,
                "in_point_ms": item.in_point_ms,
                "out_point_ms": item.out_point_ms,
                "scale": item.scale,
                "pos_x": item.pos_x,
                "pos_y": item.pos_y,
                "opacity": item.opacity,
                "brightness": item.brightness,
                "contrast": item.contrast,
                "saturation": item.saturation,
                "text_overlay": item.text_overlay,
            }
            clips.append(data)
    return TimelineState(
        clips=clips,
        muted_tracks=[t.index for t in manager.tracks if t.is_muted],
        locked_tracks=[t.index for t in manager.tracks if t.is_locked],
    )


def apply_state_to_manager(state: TimelineState, manager: TimelineManager) -> None:
    """Restore a snapshot into a manager without invoking edit validation."""
    highest = max([0] + [int(c.get("track_index", 0)) for c in state.clips])
    while len(manager.tracks) <= highest:
        index = len(manager.tracks)
        manager.tracks.append(TimelineTrack(index, f"Track {index + 1}", "video"))

    for track in manager.tracks:
        track.items.clear()
        track.is_muted = False
        track.is_locked = False

    for data in state.clips:
        item = TimelineItem(
            id=str(data.get("id") or manager._next_item_id()),
            clip_id=str(data.get("clip_id", "")),
            name=str(data.get("name", "")),
            start_ms=_start(data),
            duration_ms=_duration(data),
            track_index=int(data.get("track_index", 0)),
            in_point_ms=int(data.get("in_point_ms", 0)),
            out_point_ms=int(data.get("out_point_ms", 0)),
            scale=float(data.get("scale", 1.0)),
            pos_x=int(data.get("pos_x", 0)),
            pos_y=int(data.get("pos_y", 0)),
            opacity=float(data.get("opacity", 1.0)),
            brightness=float(data.get("brightness", 0.0)),
            contrast=float(data.get("contrast", 1.0)),
            saturation=float(data.get("saturation", 1.0)),
            text_overlay=data.get("text_overlay"),
        )
        manager.tracks[item.track_index].items.append(item)

    for track in manager.tracks:
        track.items.sort(key=lambda entry: entry.start_ms)
        track.is_muted = track.index in state.muted_tracks
        track.is_locked = track.index in state.locked_tracks
    manager._update_total_duration()
