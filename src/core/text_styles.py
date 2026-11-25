"""Text-overlay styling and FFmpeg ``drawtext`` helpers (no Qt dependency)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional


POSITIONS: Dict[str, tuple[str, str]] = {
    "center": ("(w-text_w)/2", "(h-text_h)/2"),
    "top": ("(w-text_w)/2", "20"),
    "bottom": ("(w-text_w)/2", "h-text_h-20"),
    "top-left": ("20", "20"),
    "top-right": ("w-text_w-20", "20"),
    "bottom-left": ("20", "h-text_h-20"),
    "bottom-right": ("w-text_w-20", "h-text_h-20"),
}


@dataclass
class TextStyle:
    """Styling options for a single text overlay."""

    text: str = ""
    preset: str = "centered"
    position: str = "center"
    font: str = "Sans"
    size: int = 48
    color: str = "white"
    bold: bool = False
    outline: int = 0
    outline_color: str = "black"
    box: bool = False
    box_color: str = "black@0.5"
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "preset": self.preset,
            "position": self.position,
            "font": self.font,
            "size": self.size,
            "color": self.color,
            "bold": self.bold,
            "outline": self.outline,
            "outline_color": self.outline_color,
            "box": self.box,
            "box_color": self.box_color,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
        }


TEXT_PRESETS: Dict[str, Dict[str, Any]] = {
    "centered": {"position": "center", "size": 48, "color": "white"},
    "lower_third": {
        "position": "bottom-left",
        "size": 36,
        "color": "white",
        "box": True,
        "outline": 1,
    },
    "title": {
        "position": "center",
        "size": 72,
        "color": "white",
        "bold": True,
        "outline": 2,
    },
}


def style_from_preset(
    name: str, text: str = "", **overrides: Any
) -> TextStyle:
    """Create a :class:`TextStyle` from a named preset and overrides."""
    values: Dict[str, Any] = {"preset": name, "text": text}
    values.update(TEXT_PRESETS.get(name, TEXT_PRESETS["centered"]))
    values.update(overrides)
    allowed = TextStyle().__dict__
    return TextStyle(**{k: v for k, v in values.items() if k in allowed})


def escape_drawtext(text: str) -> str:
    """Escape characters that FFmpeg's drawtext filter treats specially."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
    )


def build_drawtext(style: TextStyle) -> str:
    """Build a complete ``drawtext`` video-filter string."""
    x, y = POSITIONS.get(style.position, POSITIONS["center"])
    parts = [
        f"text='{escape_drawtext(style.text)}'",
        f"fontcolor={style.color}",
        f"fontsize={max(1, int(style.size))}",
        f"x={x}",
        f"y={y}",
    ]
    if style.bold:
        parts.append("fontweight=bold")
    if style.outline > 0:
        parts.extend(
            (f"borderw={int(style.outline)}", f"bordercolor={style.outline_color}")
        )
    if style.box:
        parts.extend(("box=1", f"boxcolor={style.box_color}", "boxborderw=6"))
    if (
        style.start_sec is not None
        and style.end_sec is not None
        and style.end_sec > style.start_sec
    ):
        parts.append(
            f"enable='between(t,{max(0.0, style.start_sec):.3f},"
            f"{max(0.0, style.end_sec):.3f})'"
        )
    return "drawtext=" + ":".join(parts)


def style_from_dict(data: Dict[str, Any]) -> TextStyle:
    """Build a style from a settings dict, tolerating unknown keys."""
    base = TextStyle()
    known = set(base.__dict__)
    return replace(base, **{k: v for k, v in data.items() if k in known})
