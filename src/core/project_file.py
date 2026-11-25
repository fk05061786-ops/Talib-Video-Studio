"""Qt-free serialization for Talib Video Studio ``.tvs`` projects.

Projects are JSON documents with an explicit schema version. Validation is
strict on structure but tolerant of unknown fields so future versions can add
data without breaking older builds. All filesystem work is guarded and returns
human-readable errors instead of raising into the GUI.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.undo import TimelineState

PROJECT_VERSION = 1
PROJECT_EXTENSION = ".tvs"
MAX_PROJECT_BYTES = 20 * 1024 * 1024


class ProjectError(ValueError):
    """A validation or I/O error with a machine-readable field name."""

    def __init__(self, message: str, field_name: str = "") -> None:
        super().__init__(message)
        self.field_name = field_name


@dataclass
class ProjectDocument:
    """Complete serializable state of a project."""

    name: str = "Untitled Project"
    timeline: TimelineState = field(default_factory=TimelineState)
    playhead_ms: int = 0
    export_settings: Dict[str, Any] = field(default_factory=dict)
    text_style: Optional[Dict[str, Any]] = None
    created_at: str = ""
    modified_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": PROJECT_VERSION,
            "name": self.name,
            "created_at": self.created_at or datetime.now().isoformat(),
            "modified_at": self.modified_at or datetime.now().isoformat(),
            "playhead_ms": int(self.playhead_ms),
            "timeline": {
                "clips": _jsonable(self.timeline.clips),
                "transitions": _jsonable(self.timeline.transitions),
                "muted_tracks": list(self.timeline.muted_tracks),
                "locked_tracks": list(self.timeline.locked_tracks),
            },
            "export_settings": _jsonable(self.export_settings),
            "text_style": _jsonable(self.text_style),
        }


def _jsonable(value: Any) -> Any:
    """Convert Paths/datetimes to JSON-safe values, keeping other structures."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectError(f"'{field_name}' must be an object", field_name)
    return value


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise ProjectError(f"'{field_name}' must be a list", field_name)
    return value


def _as_int(value: Any, field_name: str, minimum: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ProjectError(f"'{field_name}' must be an integer", field_name)
    if number < minimum:
        raise ProjectError(f"'{field_name}' must be >= {minimum}", field_name)
    return number


def deserialize_project(data: Any) -> ProjectDocument:
    """Validate a decoded document and build a :class:`ProjectDocument`."""
    root = _require_dict(data, "project")
    version = _as_int(root.get("version", 0), "version", minimum=0)
    if version < PROJECT_VERSION:
        raise ProjectError(
            f"Project version {version} is too old (this build requires "
            f"version {PROJECT_VERSION})",
            "version",
        )
    if version > PROJECT_VERSION:
        raise ProjectError(
            f"Project was created with a newer version ({version}); this "
            f"build supports version {PROJECT_VERSION}",
            "version",
        )

    timeline_data = _require_dict(root.get("timeline", {}), "timeline")
    clips: List[Dict[str, Any]] = []
    for index, raw in enumerate(_require_list(timeline_data.get("clips", []), "timeline.clips")):
        clip = _require_dict(raw, f"timeline.clips[{index}]")
        if "id" not in clip:
            raise ProjectError(f"Clip {index} is missing 'id'", "timeline.clips")
        _as_int(clip.get("start", 0), f"timeline.clips[{index}].start")
        duration = _as_int(
            clip.get("duration", clip.get("duration_ms", 0)),
            f"timeline.clips[{index}].duration",
            minimum=1,
        )
        if duration <= 0:
            raise ProjectError(f"Clip {index} has a non-positive duration", "timeline.clips")
        clips.append(dict(clip))

    transitions = [
        dict(_require_dict(raw, f"timeline.transitions[{index}]"))
        for index, raw in enumerate(
            _require_list(timeline_data.get("transitions", []), "timeline.transitions")
        )
    ]
    for index, transition in enumerate(transitions):
        for key in ("kind", "from_id", "to_id"):
            if key not in transition:
                raise ProjectError(
                    f"Transition {index} is missing '{key}'",
                    "timeline.transitions",
                )
        _as_int(transition.get("duration_ms", 0), "timeline.transitions.duration_ms")

    timeline = TimelineState(
        clips=clips,
        transitions=transitions,
        muted_tracks=[
            _as_int(value, "timeline.muted_tracks")
            for value in _require_list(timeline_data.get("muted_tracks", []), "timeline.muted_tracks")
        ],
        locked_tracks=[
            _as_int(value, "timeline.locked_tracks")
            for value in _require_list(timeline_data.get("locked_tracks", []), "timeline.locked_tracks")
        ],
    )

    export_settings = dict(
        _require_dict(root.get("export_settings", {}), "export_settings")
    )
    text_style = root.get("text_style")
    if text_style is not None:
        text_style = dict(_require_dict(text_style, "text_style"))

    return ProjectDocument(
        name=str(root.get("name", "Untitled Project")),
        timeline=timeline,
        playhead_ms=_as_int(root.get("playhead_ms", 0), "playhead_ms"),
        export_settings=export_settings,
        text_style=text_style,
        created_at=str(root.get("created_at", "")),
        modified_at=str(root.get("modified_at", "")),
    )


def serialize_project(document: ProjectDocument) -> Dict[str, Any]:
    """Validate a document by serializing then deserializing its payload."""
    payload = document.to_dict()
    deserialize_project(payload)
    return payload


def project_path(path: str | Path) -> Path:
    """Normalize a path and append ``.tvs`` when no suffix was supplied."""
    result = Path(path).expanduser()
    if not result.suffix:
        result = result.with_suffix(PROJECT_EXTENSION)
    return result


def save_project(path: str | Path, document: ProjectDocument) -> Tuple[bool, str]:
    """Atomically save a project; return ``(success, message)``."""
    target = project_path(path)
    try:
        payload = serialize_project(document)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".tvs-", suffix=".tmp", dir=str(target.parent)
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            os.replace(temporary, target)
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise
    except ProjectError as exc:
        return False, str(exc)
    except (OSError, TypeError, ValueError) as exc:
        return False, f"Could not save project: {exc}"
    return True, str(target)


def load_project(path: str | Path) -> Tuple[Optional[ProjectDocument], str]:
    """Load a project; return ``(document or None, message/warnings)``."""
    source = project_path(path)
    if not source.exists():
        return None, f"Project file not found: {source}"
    if not source.is_file():
        return None, f"Project path is not a file: {source}"
    try:
        if source.stat().st_size > MAX_PROJECT_BYTES:
            return None, f"Project file is too large (> {MAX_PROJECT_BYTES} bytes): {source}"
        with open(source, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        document = deserialize_project(payload)
    except json.JSONDecodeError as exc:
        return None, f"Corrupt project file (invalid JSON at line {exc.lineno}): {source}"
    except UnicodeDecodeError:
        return None, f"Corrupt project file (not UTF-8 text): {source}"
    except ProjectError as exc:
        return None, f"Invalid project ('{exc.field_name or 'project'}'): {exc}"
    except OSError as exc:
        return None, f"Could not read project: {exc}"

    missing = missing_media(document, source.parent)
    if missing:
        return document, (
            f"Loaded {source.name}; {len(missing)} source media file(s) missing: "
            + ", ".join(missing[:3])
        )
    return document, f"Loaded {source.name}"


def missing_media(document: ProjectDocument, base_dir: Optional[str | Path] = None) -> List[str]:
    """Return source paths referenced by clips that cannot be found."""
    result: List[str] = []
    for clip in document.timeline.clips:
        raw = clip.get("path")
        if not raw:
            continue
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute() and base_dir is not None:
            candidate = Path(base_dir) / candidate
        if not candidate.is_file():
            result.append(str(raw))
    return result
