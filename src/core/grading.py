"""Color grading parameters and FFmpeg filter builders (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


def clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* into a range, tolerating bad input."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


@dataclass(frozen=True)
class GradeSettings:
    """Grading controls in normalized ranges."""

    brightness: float = 0.0  # -1 .. 1
    contrast: float = 1.0  # 0 .. 2
    saturation: float = 1.0  # 0 .. 2
    vibrance: float = 0.0  # -1 .. 1
    warmth: float = 0.0  # -1 .. 1 (red vs blue)
    tint: float = 0.0  # -1 .. 1 (green vs magenta)

    def to_dict(self) -> Dict[str, float]:
        return {
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "vibrance": self.vibrance,
            "warmth": self.warmth,
            "tint": self.tint,
        }


def normalize_grade(data: Any = None) -> GradeSettings:
    """Build clamped :class:`GradeSettings` from a dict or settings object."""
    base = GradeSettings()
    if data is None:
        return base
    if isinstance(data, GradeSettings):
        values = data.to_dict()
    elif isinstance(data, dict):
        values = data
    else:
        values = {
            name: getattr(data, name, default)
            for name, default in base.to_dict().items()
        }
    return GradeSettings(
        brightness=clamp(values.get("brightness", 0), -1, 1),
        contrast=clamp(values.get("contrast", 1), 0, 2),
        saturation=clamp(values.get("saturation", 1), 0, 2),
        vibrance=clamp(values.get("vibrance", 0), -1, 1),
        warmth=clamp(values.get("warmth", 0), -1, 1),
        tint=clamp(values.get("tint", 0), -1, 1),
    )


def merge_grade(base: GradeSettings, overrides: Dict[str, Any]) -> GradeSettings:
    """Return *base* with specific fields replaced by *overrides*."""
    values = base.to_dict()
    for key in values:
        if key in overrides:
            values[key] = overrides[key]
    return normalize_grade(values)


def _eq_filter(settings: GradeSettings) -> str:
    return (
        "eq="
        f"brightness={float(settings.brightness)}:"
        f"contrast={float(settings.contrast)}:"
        f"saturation={float(settings.saturation)}"
    )


def build_grade_filter(data: Any = None) -> str:
    """Return the FFmpeg video filter chain for the requested grade."""
    settings = normalize_grade(data)
    filters: list[str] = []
    if (
        settings.brightness != 0
        or settings.contrast != 1
        or settings.saturation != 1
    ):
        filters.append(_eq_filter(settings))
    if settings.vibrance != 0:
        filters.append(f"vibrance=intensity={float(settings.vibrance)}")
    if settings.warmth != 0 or settings.tint != 0:
        balance = []
        if settings.warmth != 0:
            balance.extend(
                (
                    f"rm={float(settings.warmth)}",
                    f"bm={float(-settings.warmth)}",
                )
            )
        if settings.tint != 0:
            balance.append(f"gm={float(settings.tint)}")
        filters.append("colorbalance=" + ":".join(balance))
    return ",".join(filters)
