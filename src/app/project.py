"""Project state management for Talib Video Studio.

Handles project creation, media clip management, timeline sequences,
and project persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class MediaClip:
    """Represents a media clip in the project."""

    id: str
    name: str
    path: Path
    duration: float  # seconds
    resolution: str  # "widthxheight"
    fps: float
    format: str
    size: int  # bytes
    imported_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["path"] = str(self.path)
        data["imported_at"] = self.imported_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MediaClip:
        """Create from dictionary."""
        data["path"] = Path(data["path"])
        data["imported_at"] = datetime.fromisoformat(data["imported_at"])
        return cls(**data)


@dataclass
class TimelineTrack:
    """Represents a timeline track."""

    id: str
    name: str
    type: str  # "video", "audio", "subtitle"
    clips: List[Dict[str, Any]]  # clip_id, start, end, track_index

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineTrack:
        return cls(**data)


@dataclass
class Sequence:
    """Represents a timeline sequence."""

    id: str
    name: str
    duration: float
    tracks: List[TimelineTrack]
    settings: Dict[str, Any]  # resolution, fps, etc.

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tracks"] = [track.to_dict() for track in self.tracks]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Sequence:
        data["tracks"] = [TimelineTrack.from_dict(t) for t in data["tracks"]]
        return cls(**data)


class Project:
    """Manages project state and persistence."""

    def __init__(self, name: str = "Untitled Project") -> None:
        self.name = name
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.media_clips: List[MediaClip] = []
        self.sequences: List[Sequence] = []
        self.current_sequence_id: Optional[str] = None
        self.settings: Dict[str, Any] = {
            "resolution": "1920x1080",
            "fps": 30.0,
            "format": "mp4",
        }

    def add_clip(self, clip: MediaClip) -> None:
        """Add a media clip to the project."""
        self.media_clips.append(clip)
        self.modified_at = datetime.now()

    def remove_clip(self, clip_id: str) -> bool:
        """Remove a media clip from the project."""
        for i, clip in enumerate(self.media_clips):
            if clip.id == clip_id:
                del self.media_clips[i]
                self.modified_at = datetime.now()
                return True
        return False

    def get_clip(self, clip_id: str) -> Optional[MediaClip]:
        """Get a media clip by ID."""
        for clip in self.media_clips:
            if clip.id == clip_id:
                return clip
        return None

    def create_sequence(self, name: str, settings: Optional[Dict[str, Any]] = None) -> Sequence:
        """Create a new timeline sequence."""
        sequence_id = f"seq_{len(self.sequences) + 1}"
        sequence = Sequence(
            id=sequence_id,
            name=name,
            duration=0.0,
            tracks=[],
            settings=settings or self.settings.copy(),
        )
        self.sequences.append(sequence)
        self.current_sequence_id = sequence_id
        self.modified_at = datetime.now()
        return sequence

    def get_current_sequence(self) -> Optional[Sequence]:
        """Get the currently active sequence."""
        if not self.current_sequence_id:
            return None
        for seq in self.sequences:
            if seq.id == self.current_sequence_id:
                return seq
        return None

    def save_project(self, path: Path) -> bool:
        """Save project to JSON file."""
        try:
            project_data = {
                "name": self.name,
                "created_at": self.created_at.isoformat(),
                "modified_at": self.modified_at.isoformat(),
                "media_clips": [clip.to_dict() for clip in self.media_clips],
                "sequences": [seq.to_dict() for seq in self.sequences],
                "current_sequence_id": self.current_sequence_id,
                "settings": self.settings,
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=2)

            return True
        except Exception:
            return False

    def load_project(self, path: Path) -> bool:
        """Load project from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                project_data = json.load(f)

            self.name = project_data["name"]
            self.created_at = datetime.fromisoformat(project_data["created_at"])
            self.modified_at = datetime.fromisoformat(project_data["modified_at"])
            self.media_clips = [MediaClip.from_dict(clip) for clip in project_data["media_clips"]]
            self.sequences = [Sequence.from_dict(seq) for seq in project_data["sequences"]]
            self.current_sequence_id = project_data["current_sequence_id"]
            self.settings = project_data["settings"]

            return True
        except Exception:
            return False