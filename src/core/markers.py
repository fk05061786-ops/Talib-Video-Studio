"""Qt-free timeline marker and chapter data structures.

Provides marker and chapter data structures with strict validation for timestamps,
and management helpers for sorting, searching, and lookup at any given time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Marker:
    """A timeline marker or chapter mark at a specific timestamp."""

    time_ms: int
    label: str
    duration_ms: int = 0
    color: str = "#ffffff"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.time_ms < 0:
            raise ValueError("Timestamp cannot be negative.")
        if self.duration_ms < 0:
            raise ValueError("Duration cannot be negative.")
        if not self.label.strip():
            raise ValueError("Label cannot be empty.")

    @property
    def end_ms(self) -> int:
        return self.time_ms + self.duration_ms


@dataclass
class MarkerTrack:
    """A collection of markers sorted by time."""

    markers: List[Marker] = field(default_factory=list)

    def add_marker(self, marker: Marker) -> None:
        """Add a marker and keep the collection sorted."""
        self.markers.append(marker)
        self.markers.sort(key=lambda m: m.time_ms)

    def remove_marker_at(self, time_ms: int) -> bool:
        """Remove the marker at the exact time_ms, if it exists."""
        initial_count = len(self.markers)
        self.markers = [m for m in self.markers if m.time_ms != time_ms]
        return len(self.markers) < initial_count

    def find_nearest(self, time_ms: int) -> Optional[Marker]:
        """Find the marker closest to the given time_ms."""
        if not self.markers:
            return None
        return min(self.markers, key=lambda m: abs(m.time_ms - time_ms))

    def find_previous(self, time_ms: int) -> Optional[Marker]:
        """Find the last marker before or at the given time_ms."""
        candidates = [m for m in self.markers if m.time_ms <= time_ms]
        return candidates[-1] if candidates else None

    def find_next(self, time_ms: int) -> Optional[Marker]:
        """Find the first marker after or at the given time_ms."""
        candidates = [m for m in self.markers if m.time_ms >= time_ms]
        return candidates[0] if candidates else None

    def find_active_chapter(self, time_ms: int) -> Optional[Marker]:
        """Find the chapter marker active at the given time_ms (using duration)."""
        for m in self.markers:
            if m.time_ms <= time_ms < m.end_ms:
                return m
        return None
