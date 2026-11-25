"""Qt-free integration helpers joining timeline, viewport and annotation modules.

These helpers let the UI combine clips, markers, subtitles and keyframes without
changing any existing module's API or the ``.tvs`` schema.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.core.keyframes import Keyframe, KeyframeTrack
from src.core.markers import Marker, MarkerTrack
from src.core.subtitles import SubtitleCue, SubtitleTrack
from src.core.timeline_ops import _duration, _start
from src.core.viewport import ViewportState, calculate_visible_range, zoom_to_fit


def timeline_extent(clips: Iterable[Any]) -> Tuple[int, int]:
    """Return the ``(start_ms, end_ms)`` span of a clip collection."""
    starts: List[int] = []
    ends: List[int] = []
    for clip in clips:
        start = _start(clip)
        starts.append(start)
        ends.append(start + _duration(clip))
    if not starts:
        return 0, 0
    return min(starts), max(ends)


def viewport_for_clips(
    clips: Iterable[Any], view_width: int, padding_ms: int = 1000
) -> ViewportState:
    """Build a viewport state that fits the supplied clips."""
    _start_ms, end_ms = timeline_extent(clips)
    return zoom_to_fit(end_ms, max(1, int(view_width)), padding_ms)


def markers_from_data(data: Iterable[Dict[str, Any]]) -> MarkerTrack:
    """Build a marker track, skipping malformed entries instead of raising."""
    track = MarkerTrack()
    for entry in data or ():
        try:
            track.add_marker(
                Marker(
                    time_ms=int(entry["time_ms"]),
                    label=str(entry.get("label", "Marker")),
                    duration_ms=int(entry.get("duration_ms", 0)),
                    color=str(entry.get("color", "#ffffff")),
                    notes=str(entry.get("notes", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return track


def subtitles_from_data(data: Iterable[Dict[str, Any]]) -> SubtitleTrack:
    """Build a subtitle track, skipping malformed or overlapping cues."""
    track = SubtitleTrack()
    for entry in data or ():
        try:
            track.add_cue(
                SubtitleCue(
                    start_ms=int(entry["start_ms"]),
                    end_ms=int(entry["end_ms"]),
                    text=str(entry["text"]),
                    speaker=entry.get("speaker"),
                    style=entry.get("style"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return track


def keyframes_from_data(
    data: Dict[str, Sequence[Dict[str, Any]]],
) -> Dict[str, KeyframeTrack]:
    """Build keyframe tracks keyed by parameter name, skipping bad entries."""
    result: Dict[str, KeyframeTrack] = {}
    for name, entries in (data or {}).items():
        track = KeyframeTrack(name=name)
        for entry in entries:
            try:
                track.add_keyframe(
                    int(entry["time_ms"]),
                    float(entry["value"]),
                    str(entry.get("interpolation", "linear")),
                )
            except (KeyError, TypeError, ValueError):
                continue
        result[name] = track
    return result


def keyframes_to_data(
    tracks: Dict[str, KeyframeTrack],
) -> Dict[str, List[Dict[str, Any]]]:
    """Serialize keyframe tracks to plain JSON-compatible data."""
    return {
        name: [
            {
                "time_ms": kf.time_ms,
                "value": kf.value,
                "interpolation": kf.interpolation,
            }
            for kf in track.keyframes
        ]
        for name, track in tracks.items()
    }


def active_values_at(
    tracks: Dict[str, KeyframeTrack], time_ms: int
) -> Dict[str, float]:
    """Evaluate every keyframe track at *time_ms*."""
    return {name: track.evaluate(time_ms) for name, track in tracks.items()}


def integration_status(
    clips: Iterable[Any],
    markers: Optional[MarkerTrack] = None,
    subtitles: Optional[SubtitleTrack] = None,
    keyframes: Optional[Dict[str, KeyframeTrack]] = None,
    playhead_ms: int = 0,
    view_width: int = 800,
) -> Dict[str, Any]:
    """Summarize combined timeline/annotation state for a status readout."""
    extent_start, extent_end = timeline_extent(clips)
    visible = calculate_visible_range(
        viewport_for_clips(clips, view_width)
    )
    next_marker = markers.find_next(playhead_ms) if markers else None
    cue = subtitles.find_at(playhead_ms) if subtitles else None
    return {
        "playhead_ms": max(0, int(playhead_ms)),
        "timeline_start_ms": extent_start,
        "timeline_end_ms": extent_end,
        "visible_range": list(visible),
        "next_marker_ms": next_marker.time_ms if next_marker else None,
        "subtitle_text": cue.text if cue else "",
        "keyframe_values": active_values_at(keyframes or {}, playhead_ms),
    }
