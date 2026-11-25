"""Transition helpers for timeline clips and export (no Qt dependency)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class Transition:
    """A transition between two clips on the same track."""

    kind: str  # "crossfade" or "dissolve"
    duration_ms: int
    from_id: str
    to_id: str
    track_index: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "duration_ms": self.duration_ms,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "track_index": self.track_index,
        }


def clip_range(clip: Any) -> tuple[int, int]:
    """Return ``(start_ms, end_ms)`` for a dict or dataclass clip."""
    if isinstance(clip, dict):
        start = int(clip.get("start", clip.get("start_ms", 0)))
        duration = int(clip.get("duration", clip.get("duration_ms", 0)))
    else:
        start = int(getattr(clip, "start_ms", 0))
        duration = int(getattr(clip, "duration_ms", 0))
    return start, start + duration


def overlap_ms(first: Any, second: Any) -> int:
    """Return the overlap of two clips in milliseconds (zero when disjoint)."""
    a_start, a_end = clip_range(first)
    b_start, b_end = clip_range(second)
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def make_transition(
    first: Any,
    second: Any,
    max_duration_ms: int,
    kind: str = "crossfade",
) -> Optional[Transition]:
    """Build a transition capped by the clips' actual overlap."""
    if kind not in ("crossfade", "dissolve"):
        return None
    available = overlap_ms(first, second)
    duration = min(max(0, max_duration_ms), available)
    if duration <= 0:
        return None

    def get_id(clip: Any) -> str:
        if isinstance(clip, dict):
            return str(clip.get("id", ""))
        return str(getattr(clip, "id", ""))

    def get_track(clip: Any) -> int:
        if isinstance(clip, dict):
            return int(clip.get("track_index", 0))
        return int(getattr(clip, "track_index", 0))

    return Transition(kind, duration, get_id(first), get_id(second), get_track(first))


def xfade_offsets(
    duration_ms: Sequence[int], transition_ms: Sequence[int]
) -> List[float]:
    """Return cumulative FFmpeg ``xfade`` offsets in seconds."""
    if len(transition_ms) != max(0, len(duration_ms) - 1):
        return []
    offsets: List[float] = []
    elapsed = 0
    for index, overlap in enumerate(transition_ms):
        elapsed += duration_ms[index]
        elapsed -= overlap
        offsets.append(max(0, elapsed) / 1000.0)
    return offsets
