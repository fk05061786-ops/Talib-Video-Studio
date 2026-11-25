"""Qt-free keyframe evaluation and parameter interpolation for Talib Video Studio.

Provides parameter keyframing data structures and deterministic interpolation
helpers (linear, hold/step, smoothstep, ease-in, ease-out) without any Qt dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class Keyframe:
    """A single keyframe at a specific timestamp in milliseconds."""

    time_ms: int
    value: float
    interpolation: str = "linear"  # "linear", "hold", "ease_in", "ease_out", "smoothstep"


def _smoothstep(t: float) -> float:
    """Standard smoothstep interpolation t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_in(t: float) -> float:
    """Quadratic ease-in interpolation t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t


def _ease_out(t: float) -> float:
    """Quadratic ease-out interpolation t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * (2.0 - t)


def interpolate_keyframe_pair(
    k1: Keyframe, k2: Keyframe, time_ms: int
) -> float:
    """Interpolate between two keyframes k1 and k2 at time_ms."""
    if k1.time_ms == k2.time_ms:
        return k2.value

    if time_ms <= k1.time_ms:
        return k1.value
    if time_ms >= k2.time_ms:
        return k2.value

    # Normalize t into [0, 1]
    t = (time_ms - k1.time_ms) / float(k2.time_ms - k1.time_ms)

    interp_type = k1.interpolation.lower()

    if interp_type == "hold" or interp_type == "step":
        return k1.value
    elif interp_type == "ease_in":
        factor = _ease_in(t)
    elif interp_type == "ease_out":
        factor = _ease_out(t)
    elif interp_type == "smoothstep":
        factor = _smoothstep(t)
    else:  # default to linear
        factor = t

    return k1.value + (k2.value - k1.value) * factor


@dataclass
class KeyframeTrack:
    """A collection of keyframes for a single parameter over time."""

    name: str = "parameter"
    default_value: float = 0.0
    keyframes: List[Keyframe] = field(default_factory=list)

    def add_keyframe(
        self, time_ms: int, value: float, interpolation: str = "linear"
    ) -> None:
        """Add or update a keyframe at time_ms, keeping keyframes sorted."""
        # Replace existing keyframe at same time if present
        self.keyframes = [k for k in self.keyframes if k.time_ms != time_ms]
        kf = Keyframe(
            time_ms=int(time_ms),
            value=float(value),
            interpolation=str(interpolation),
        )
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.time_ms)

    def remove_keyframe_at(self, time_ms: int) -> bool:
        """Remove keyframe at exactly time_ms. Returns True if found & removed."""
        original_count = len(self.keyframes)
        self.keyframes = [k for k in self.keyframes if k.time_ms != time_ms]
        return len(self.keyframes) < original_count

    def evaluate(self, time_ms: int) -> float:
        """Evaluate parameter value at time_ms."""
        if not self.keyframes:
            return self.default_value

        # Time before or at first keyframe
        if time_ms <= self.keyframes[0].time_ms:
            return self.keyframes[0].value

        # Time at or after last keyframe
        if time_ms >= self.keyframes[-1].time_ms:
            return self.keyframes[-1].value

        # Find enclosing pair
        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i + 1]
            if k1.time_ms <= time_ms <= k2.time_ms:
                return interpolate_keyframe_pair(k1, k2, time_ms)

        return self.default_value
