"""Frame-accurate timecode helpers for monitor playback and scrubbing.

This module is intentionally free of Qt imports so the timing logic can be
unit-tested on a headless machine without PySide6 or a display.
"""

from __future__ import annotations


def ms_to_frames(ms: int, fps: float) -> int:
    """Convert a millisecond position to the nearest frame index."""
    return int(round((ms / 1000.0) * fps))


def frames_to_ms(frames: int, fps: float) -> int:
    """Convert a frame index back to a millisecond position."""
    if fps <= 0:
        return 0
    return int(round((frames / fps) * 1000.0))


def step_frames(ms: int, delta_frames: int, fps: float) -> int:
    """Return the position *delta_frames* frames before/after *ms*."""
    return frames_to_ms(ms_to_frames(ms, fps) + delta_frames, fps)


def step_position(ms: int, delta_frames: int, fps: float, duration_ms: int = 0) -> int:
    """Step by whole frames, clamped to ``[0, duration_ms]`` when known."""
    target = max(0, step_frames(ms, delta_frames, fps))
    if duration_ms > 0:
        target = min(target, duration_ms)
    return target


def format_timecode(ms: int, fps: float = 30.0) -> str:
    """Format *ms* as a frame-accurate ``HH:MM:SS:FF`` timecode."""
    frames_per_sec = max(1, int(round(fps)))
    total_frames = ms_to_frames(ms, fps)
    frames_per_min = frames_per_sec * 60
    frames_per_hour = frames_per_min * 60
    hours, remainder = divmod(total_frames, frames_per_hour)
    minutes, remainder = divmod(remainder, frames_per_min)
    seconds, frames = divmod(remainder, frames_per_sec)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
