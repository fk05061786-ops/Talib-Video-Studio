"""Pure timeline geometry and edit helpers.

No Qt imports here: drag snapping, overlap resolution, trimming, rippling and
razor splits are all plain data operations so they can be unit-tested on a
headless machine without PySide6 or a display. Clips may be dicts (UI data)
or dataclass-like objects (core ``TimelineItem``).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def clamp(value: int, low: int, high: int) -> int:
    """Clamp *value* into ``[low, high]`` (tolerating a reversed range)."""
    if high < low:
        high = low
    return max(low, min(high, value))


def _value(clip: Any, *keys: str, default: Any = None) -> Any:
    """Read the first available key from a dict or dataclass-like clip."""
    if isinstance(clip, dict):
        for key in keys:
            if key in clip:
                return clip[key]
    else:
        for key in keys:
            if hasattr(clip, key):
                return getattr(clip, key)
    return default


def _start(clip: Any) -> int:
    return int(_value(clip, "start", "start_ms", default=0))


def _duration(clip: Any) -> int:
    return int(_value(clip, "duration", "duration_ms", default=0))


def ms_from_x(x: float, ms_to_px: float) -> int:
    """Convert a scene x-coordinate to milliseconds."""
    if ms_to_px <= 0:
        return 0
    return max(0, int(round(x / ms_to_px)))


def track_from_y(
    y: float, track_count: int, track_height: int = 80, top_offset: int = 5
) -> int:
    """Convert a scene y-coordinate to a clamped track index."""
    if track_count <= 0:
        return 0
    index = int(round((y - top_offset) / track_height))
    return clamp(index, 0, track_count - 1)


def snap_position(
    position_ms: int, targets: Iterable[int], threshold_ms: int
) -> int:
    """Snap *position_ms* to the nearest target within *threshold_ms*."""
    if threshold_ms <= 0:
        return position_ms
    closest: Optional[int] = None
    distance = threshold_ms + 1
    for target in targets:
        delta = abs(target - position_ms)
        if delta < distance:
            closest, distance = target, delta
    return closest if closest is not None and distance <= threshold_ms else position_ms


def clip_edges(clips: Iterable[Any], ignore_id: Optional[str] = None) -> List[int]:
    """Collect start/end times of clips, optionally skipping one clip."""
    edges: List[int] = []
    for clip in clips:
        if ignore_id is not None and _value(clip, "id", default=None) == ignore_id:
            continue
        start = _start(clip)
        edges.extend((start, start + _duration(clip)))
    return edges


def overlapping_clip(
    clips: Iterable[Any],
    start_ms: int,
    end_ms: int,
    ignore_id: Optional[str] = None,
    track_index: Optional[int] = None,
) -> Optional[str]:
    """Return the id of the first clip overlapping ``[start_ms, end_ms)``."""
    for clip in clips:
        if ignore_id is not None and _value(clip, "id", default=None) == ignore_id:
            continue
        if track_index is not None and _value(
            clip, "track_index", default=None
        ) != track_index:
            continue
        other_start = _start(clip)
        other_end = other_start + _duration(clip)
        if start_ms < other_end and other_start < end_ms:
            return _value(clip, "id", default=None)
    return None


def resolve_move(
    start_ms: int,
    duration_ms: int,
    target_track: int,
    clips: Sequence[Any],
    snap_points: Iterable[int],
    threshold_ms: int,
    ignore_id: Optional[str] = None,
) -> Optional[int]:
    """Return a snapped, overlap-free start for a move, or ``None`` if blocked."""
    snapped = snap_position(max(0, start_ms), snap_points, threshold_ms)
    if overlapping_clip(
        clips, snapped, snapped + duration_ms, ignore_id, target_track
    ) is not None:
        return None
    return snapped


def trim_bounds(
    start_ms: int,
    duration_ms: int,
    edge: str,
    delta_ms: int,
    min_duration_ms: int = 1,
) -> Tuple[int, int]:
    """Return ``(start, duration)`` after dragging *edge* by *delta_ms*."""
    end_ms = start_ms + duration_ms
    if edge == "start":
        new_start = clamp(start_ms + delta_ms, 0, end_ms - min_duration_ms)
        return new_start, end_ms - new_start
    if edge == "end":
        new_end = max(end_ms + delta_ms, start_ms + min_duration_ms)
        return start_ms, new_end - start_ms
    return start_ms, duration_ms


def resolve_trim(
    start_ms: int,
    duration_ms: int,
    edge: str,
    delta_ms: int,
    target_track: int,
    clips: Sequence[Any],
    snap_points: Iterable[int],
    threshold_ms: int,
    ignore_id: Optional[str] = None,
    min_duration_ms: int = 1,
) -> Optional[Tuple[int, int]]:
    """Return snapped, overlap-free ``(start, duration)`` or ``None``."""
    new_start, new_duration = trim_bounds(
        start_ms, duration_ms, edge, delta_ms, min_duration_ms
    )
    if edge == "start":
        new_start = snap_position(new_start, snap_points, threshold_ms)
        new_start = clamp(new_start, 0, start_ms + duration_ms - min_duration_ms)
        new_duration = start_ms + duration_ms - new_start
    else:
        snapped_end = snap_position(
            new_start + new_duration, snap_points, threshold_ms
        )
        new_duration = max(snapped_end - new_start, min_duration_ms)

    if overlapping_clip(
        clips,
        new_start,
        new_start + new_duration,
        ignore_id,
        target_track,
    ) is not None:
        return None
    return new_start, new_duration


def ripple_shift(
    clips: Iterable[Any],
    from_ms: int,
    delta_ms: int,
    ignore_ids: Sequence[str] = (),
) -> List[Tuple[str, int]]:
    """Return ``(id, new_start)`` updates for clips beginning at/after a point."""
    if delta_ms == 0:
        return []
    updates: List[Tuple[str, int]] = []
    for clip in clips:
        clip_id = _value(clip, "id", default=None)
        if clip_id is None or clip_id in ignore_ids:
            continue
        if _start(clip) >= from_ms:
            updates.append((clip_id, max(0, _start(clip) + delta_ms)))
    return updates


def razor_segments(
    start_ms: int,
    duration_ms: int,
    split_ms: int,
    in_point_ms: int = 0,
    out_point_ms: int = 0,
) -> List[Tuple[int, int, int, int]]:
    """Split a clip into ``(start, duration, in, out)`` segments."""
    end_ms = start_ms + duration_ms
    if not start_ms < split_ms < end_ms:
        return []
    first = split_ms - start_ms
    return [
        (start_ms, first, in_point_ms, in_point_ms + first),
        (split_ms, end_ms - split_ms, in_point_ms + first, out_point_ms),
    ]


def _with_start(clip: Any, start_ms: int) -> Any:
    """Return a copy of *clip* with its start moved to *start_ms*."""
    if isinstance(clip, dict):
        updated = dict(clip)
        updated["start"] = start_ms
        if "start_ms" in updated:
            updated["start_ms"] = start_ms
        return updated
    return replace(clip, start_ms=start_ms)


def ripple_delete_plan(
    clips: Sequence[Any],
    item_id: str,
    locked_ids: Sequence[str] = (),
) -> Tuple[Optional[Any], List[Tuple[str, int]]]:
    """Plan a ripple delete: remove *item_id*, pull later same-track clips left."""
    target = next(
        (clip for clip in clips if _value(clip, "id", default=None) == item_id),
        None,
    )
    if target is None or item_id in locked_ids:
        return None, []
    duration = _duration(target)
    if duration <= 0:
        return target, []
    track = _value(target, "track_index", default=0)
    peers = [
        clip
        for clip in clips
        if _value(clip, "id", default=None) != item_id
        and _value(clip, "id", default=None) not in locked_ids
        and _value(clip, "track_index", default=0) == track
    ]
    shifts = ripple_shift(
        peers,
        _start(target) + duration,
        -duration,
        (item_id,),
    )
    return target, shifts


def apply_ripple_plan(
    clips: Sequence[Any], item_id: str, shifts: Sequence[Tuple[str, int]]
) -> List[Any]:
    """Apply a ripple-delete plan to a clip collection without mutating inputs."""
    updates = dict(shifts)
    result: List[Any] = []
    for clip in clips:
        clip_id = _value(clip, "id", default=None)
        if clip_id == item_id:
            continue
        result.append(_with_start(clip, updates[clip_id]) if clip_id in updates else clip)
    return result
