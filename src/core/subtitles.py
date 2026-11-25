"""Qt-free subtitle cue data structures and validation.

Provides subtitle cue/caption data structures with time validation (start/end)
and helper methods for sorting, overlap checking, and lookup at any given time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SubtitleCue:
    """A single subtitle cue with timing and text."""

    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None
    style: Optional[str] = None

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("Start time cannot be negative.")
        if self.end_ms <= self.start_ms:
            raise ValueError("End time must be greater than start time.")
        if not self.text.strip():
            raise ValueError("Subtitle text cannot be empty.")


@dataclass
class SubtitleTrack:
    """A collection of subtitle cues, validated to be non-overlapping and sorted."""

    cues: List[SubtitleCue] = field(default_factory=list)

    def add_cue(self, cue: SubtitleCue) -> None:
        """Add a cue and re-sort, ensuring no overlaps."""
        if self.overlaps(cue.start_ms, cue.end_ms):
            raise ValueError(f"Cue {cue.start_ms}-{cue.end_ms} overlaps existing cues.")
        self.cues.append(cue)
        self.cues.sort(key=lambda c: c.start_ms)

    def overlaps(self, start_ms: int, end_ms: int) -> bool:
        """Return True if the given range overlaps any cue in the track."""
        for cue in self.cues:
            if start_ms < cue.end_ms and end_ms > cue.start_ms:
                return True
        return False

    def find_at(self, time_ms: int) -> Optional[SubtitleCue]:
        """Find the active cue at a given timestamp."""
        for cue in self.cues:
            if cue.start_ms <= time_ms < cue.end_ms:
                return cue
        return None

    def get_sorted(self) -> List[SubtitleCue]:
        """Return cues sorted by start time."""
        return sorted(self.cues, key=lambda c: c.start_ms)


def format_srt_time(ms: int) -> str:
    """Format milliseconds into SRT time format: HH:MM:SS,mmm."""
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
