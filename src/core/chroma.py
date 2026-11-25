"""Chroma key parameters and FFmpeg filter builders (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


CHROMA_PRESETS: Dict[str, Dict[str, Any]] = {
    "green_screen": {"color": "green", "similarity": 0.2, "blend": 0.05},
    "blue_screen": {"color": "blue", "similarity": 0.2, "blend": 0.05},
    "custom": {"color": "green", "similarity": 0.15, "blend": 0.05},
}

_NAMED_COLORS = {
    "green": "0x00FF00",
    "blue": "0x0000FF",
    "white": "0xFFFFFF",
    "black": "0x000000",
}


@dataclass(frozen=True)
class ChromaSettings:
    """Settings for keying a solid background out of a clip."""

    enabled: bool = False
    color: str = "green"
    similarity: float = 0.2
    blend: float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color": self.color,
            "similarity": self.similarity,
            "blend": self.blend,
        }


def normalize_chroma(data: Any = None) -> ChromaSettings:
    """Build clamped :class:`ChromaSettings` from a dict or settings object."""
    base = ChromaSettings()
    if data is None:
        return base
    if isinstance(data, ChromaSettings):
        values = data.to_dict()
    elif isinstance(data, dict):
        values = data
    else:
        values = {
            "enabled": getattr(data, "enabled", False),
            "color": getattr(data, "color", "green"),
            "similarity": getattr(data, "similarity", 0.2),
            "blend": getattr(data, "blend", 0.05),
        }
    return ChromaSettings(
        enabled=bool(values.get("enabled", False)),
        color=str(values.get("color", "green") or "green"),
        similarity=_clamp_unit(values.get("similarity", 0.2)),
        blend=_clamp_unit(values.get("blend", 0.05)),
    )


def _clamp_unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))


def ffmpeg_color(color: str) -> str:
    """Convert a preset name or ``#RRGGBB`` into an FFmpeg color token."""
    key = str(color).strip().lower()
    if key in _NAMED_COLORS:
        return _NAMED_COLORS[key]
    if key.startswith("#") and len(key) == 7:
        return "0x" + key[1:].upper()
    if key.startswith("0x"):
        return key.upper()
    return _NAMED_COLORS["green"]


def build_chroma_filter(data: Any = None) -> str:
    """Return a ``chromakey`` filter string, or ``""`` when disabled."""
    settings = normalize_chroma(data)
    if not settings.enabled:
        return ""
    return (
        "chromakey="
        f"color={ffmpeg_color(settings.color)}:"
        f"similarity={float(settings.similarity)}:"
        f"blend={float(settings.blend)}"
    )
