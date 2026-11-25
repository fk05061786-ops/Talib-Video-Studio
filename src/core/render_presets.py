"""Qt-free standard NLE export presets for Talib Video Studio.

Provides render presets (YouTube, Shorts, Drafts) with strict validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RenderPreset:
    """Settings for a specific export target."""

    name: str
    width: int
    height: int
    fps: float
    video_bitrate: str = "8M"
    audio_bitrate: str = "128k"
    codec: str = "libx264"
    audio_codec: str = "aac"

    def __post_init__(self) -> None:
        """Validate preset parameters."""
        if self.width <= 0 or self.width % 2 != 0:
            raise ValueError(f"Width must be positive and even: {self.width}")
        if self.height <= 0 or self.height % 2 != 0:
            raise ValueError(f"Height must be positive and even: {self.height}")
        if self.fps <= 0:
            raise ValueError(f"FPS must be positive: {self.fps}")


PRESETS: Dict[str, RenderPreset] = {
    "youtube_1080p": RenderPreset("YouTube 1080p", 1920, 1080, 30.0, "12M"),
    "youtube_1080p_60": RenderPreset("YouTube 1080p60", 1920, 1080, 60.0, "15M"),
    "youtube_4k": RenderPreset("YouTube 4K", 3840, 2160, 30.0, "45M"),
    "shorts_9_16": RenderPreset("Shorts/Reels 1080x1920", 1080, 1920, 30.0, "12M"),
    "draft_720p": RenderPreset("Draft Preview 720p", 1280, 720, 30.0, "5M"),
}


def get_preset(key: str) -> Optional[RenderPreset]:
    """Return a preset by key or None."""
    return PRESETS.get(key.lower())


def list_presets() -> Dict[str, str]:
    """Return a map of key to descriptive name."""
    return {k: p.name for k, p in PRESETS.items()}


def preset_choices() -> Dict[str, Optional[str]]:
    """Return UI labels mapped to preset keys (``None`` for custom)."""
    choices: Dict[str, Optional[str]] = {"Custom": None}
    for key, name in list_presets().items():
        choices[name] = key
    return choices


def preset_to_export_settings(key: str) -> Optional[Dict[str, Any]]:
    """Convert a preset key into export settings, or ``None`` when unknown."""
    preset = get_preset(str(key))
    if preset is None:
        return None
    return {
        "preset": str(key).lower(),
        "resolution": f"{preset.width}x{preset.height}",
        "fps": int(preset.fps),
        "video_bitrate": preset.video_bitrate,
        "audio_bitrate": preset.audio_bitrate,
        "codec": preset.codec,
        "audio_codec": preset.audio_codec,
    }
