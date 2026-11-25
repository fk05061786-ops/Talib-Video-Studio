"""Timeline core operations for Talib Video Studio.

Manages timeline tracks, clips, playback positioning, and sequencing.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, replace

from src.core.timeline_ops import overlapping_clip


@dataclass
class TimelineItem:
    """Represents a clip instance placed on a timeline track."""
    id: str
    clip_id: str
    name: str
    start_ms: int
    duration_ms: int
    track_index: int
    in_point_ms: int = 0
    out_point_ms: int = 0
    # Effects
    scale: float = 1.0
    pos_x: int = 0
    pos_y: int = 0
    opacity: float = 1.0
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    text_overlay: Optional[str] = None

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass
class TimelineTrack:
    """Represents a single track on the timeline (video or audio)."""
    index: int
    name: str
    track_type: str = "video"  # "video" or "audio"
    items: List[TimelineItem] = field(default_factory=list)
    is_muted: bool = False
    is_locked: bool = False

    def add_item(self, item: TimelineItem) -> None:
        if self.is_locked:
            return
        self.items.append(item)
        # Sort items by start time
        self.items.sort(key=lambda x: x.start_ms)

    def remove_item(self, item_id: str) -> bool:
        if self.is_locked:
            return False
        for i, item in enumerate(self.items):
            if item.id == item_id:
                del self.items[i]
                return True
        return False


class TimelineManager:
    """Manages multi-track timeline sequencing and playback head."""

    def __init__(self, allow_overlap: bool = False) -> None:
        self.allow_overlap = allow_overlap
        self.tracks: List[TimelineTrack] = [
            TimelineTrack(0, "Video 1", "video"),
            TimelineTrack(1, "Audio 1", "audio"),
        ]
        self.playhead_ms: int = 0
        self.duration_ms: int = 0

    def add_clip_to_track(
        self,
        clip_id: str,
        name: str,
        track_index: int,
        start_ms: int,
        duration_ms: int,
    ) -> Optional[TimelineItem]:
        """Add a clip item to the specified timeline track."""
        while track_index >= len(self.tracks):
            self.tracks.append(
                TimelineTrack(len(self.tracks), f"Track {len(self.tracks)+1}", "video")
            )

        if self.tracks[track_index].is_locked:
            return None

        if not self.allow_overlap and overlapping_clip(
            self.tracks[track_index].items,
            start_ms,
            start_ms + duration_ms,
            track_index=track_index,
        ) is not None:
            return None

        item = TimelineItem(
            id=self._next_item_id(),
            clip_id=clip_id,
            name=name,
            start_ms=start_ms,
            duration_ms=duration_ms,
            track_index=track_index,
            out_point_ms=duration_ms,
        )
        self.tracks[track_index].add_item(item)
        self._update_total_duration()
        return item

    def _next_item_id(self) -> str:
        """Return an ID that is unique across every track."""
        used = {itm.id for track in self.tracks for itm in track.items}
        n = 1
        while f"item_{n}" in used:
            n += 1
        return f"item_{n}"

    def move_item(self, item_id: str, new_track_index: int, new_start_ms: int) -> bool:
        """Move a clip item to a new track/start time."""
        item = None
        old_track = None
        for track in self.tracks:
            for itm in track.items:
                if itm.id == item_id:
                    item = itm
                    old_track = track
                    break
            if item: break

        if not item or old_track.is_locked: return False

        if new_track_index >= len(self.tracks) or self.tracks[new_track_index].is_locked:
            return False

        if not self.allow_overlap and overlapping_clip(
            self.tracks[new_track_index].items,
            new_start_ms,
            new_start_ms + item.duration_ms,
            ignore_id=item_id,
            track_index=new_track_index,
        ) is not None:
            return False

        # Move the existing item so its effects and in/out points survive
        old_track.remove_item(item_id)
        item.start_ms = new_start_ms
        item.track_index = new_track_index
        new_track = self.tracks[new_track_index]
        new_track.items.append(item)
        new_track.items.sort(key=lambda x: x.start_ms)
        self._update_total_duration()
        return True

    def split_item(self, item_id: str, split_ms: int) -> Optional[List[TimelineItem]]:
        """Split a timeline item at *split_ms* relative to the track start."""
        item = None
        track = None
        for t in self.tracks:
            for itm in t.items:
                if itm.id == item_id:
                    item = itm
                    track = t
                    break
            if item: break

        if not item or track.is_locked or not (item.start_ms < split_ms < item.end_ms):
            return None

        # Remove the original, then clone it with adjusted bounds/effects
        track.remove_item(item_id)

        dur1 = split_ms - item.start_ms
        first = replace(
            item,
            id=self._next_item_id(),
            duration_ms=dur1,
            out_point_ms=item.in_point_ms + dur1,
        )
        second = replace(
            item,
            id=self._next_item_id(),
            start_ms=split_ms,
            duration_ms=item.end_ms - split_ms,
            in_point_ms=item.in_point_ms + dur1,
        )
        track.items.extend([first, second])
        track.items.sort(key=lambda x: x.start_ms)
        self._update_total_duration()
        return [first, second]

    def trim_item(self, item_id: str, new_start_ms: int, new_end_ms: int) -> bool:
        """Trim an item's bounds."""
        for track in self.tracks:
            if track.is_locked: continue
            for item in track.items:
                if item.id == item_id:
                    if new_end_ms <= new_start_ms:
                        return False
                    if not self.allow_overlap and overlapping_clip(
                        track.items,
                        new_start_ms,
                        new_end_ms,
                        ignore_id=item_id,
                        track_index=track.index,
                    ) is not None:
                        return False
                    item.start_ms = new_start_ms
                    item.duration_ms = new_end_ms - new_start_ms
                    self._update_total_duration()
                    return True
        return False

    def set_playhead(self, position_ms: int) -> None:
        """Set playhead position in milliseconds."""
        self.playhead_ms = max(0, position_ms)

    def _update_total_duration(self) -> None:
        """Recalculate total sequence duration."""
        max_end = 0
        for track in self.tracks:
            for item in track.items:
                if item.end_ms > max_end:
                    max_end = item.end_ms
        self.duration_ms = max_end