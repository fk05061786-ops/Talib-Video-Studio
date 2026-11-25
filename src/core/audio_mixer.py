"""Qt-free audio mixer settings and FFmpeg filter builders.

Provides multi-track audio mix parameters (dB to linear gain), safe clamping,
fade-in/out filter builders, and normalization filter helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def db_to_linear(db: float) -> float:
    """Convert decibels to linear gain (factor)."""
    return 10.0 ** (db / 20.0)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value to range [low, high]."""
    return max(low, min(high, value))


@dataclass(frozen=True)
class AudioMixSettings:
    """Multi-track audio mix parameters."""

    gain_db: float = 0.0  # -60 to 12
    mute: bool = False
    solo: bool = False
    fade_in_ms: int = 0
    fade_out_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gain_db": self.gain_db,
            "mute": self.mute,
            "solo": self.solo,
            "fade_in_ms": self.fade_in_ms,
            "fade_out_ms": self.fade_out_ms,
        }


def normalize_audio_settings(data: Any = None) -> AudioMixSettings:
    """Build validated :class:`AudioMixSettings` from input."""
    base = AudioMixSettings()
    if data is None:
        return base
    if isinstance(data, AudioMixSettings):
        values = data.to_dict()
    elif isinstance(data, dict):
        values = data
    else:
        values = {
            "gain_db": getattr(data, "gain_db", 0.0),
            "mute": getattr(data, "mute", False),
            "solo": getattr(data, "solo", False),
            "fade_in_ms": getattr(data, "fade_in_ms", 0),
            "fade_out_ms": getattr(data, "fade_out_ms", 0),
        }
    return AudioMixSettings(
        gain_db=clamp(float(values.get("gain_db", 0.0)), -60.0, 12.0),
        mute=bool(values.get("mute", False)),
        solo=bool(values.get("solo", False)),
        fade_in_ms=max(0, int(values.get("fade_in_ms", 0))),
        fade_out_ms=max(0, int(values.get("fade_out_ms", 0))),
    )


def build_audio_filter(settings: AudioMixSettings, duration_ms: Optional[int] = None) -> str:
    """Build FFmpeg audio filter chain string."""
    filters = []

    if settings.mute:
        filters.append("volume=0")
    elif settings.gain_db != 0.0:
        filters.append(f"volume={db_to_linear(settings.gain_db)}")

    if settings.fade_in_ms > 0:
        filters.append(f"afade=t=in:st=0:d={settings.fade_in_ms/1000.0:.3f}")

    if settings.fade_out_ms > 0 and duration_ms:
        start_time = (duration_ms - settings.fade_out_ms) / 1000.0
        filters.append(f"afade=t=out:st={start_time:.3f}:d={settings.fade_out_ms/1000.0:.3f}")

    return ",".join(filters)


def build_loudness_filter(integrated_target: float = -23.0, true_peak: float = -1.0) -> str:
    """Build FFmpeg loudness normalization filter."""
    return f"loudnorm=I={integrated_target}:TP={true_peak}:LRA=11"
