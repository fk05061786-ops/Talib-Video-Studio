"""Qt-free viewport/zoom geometry for Talib Video Studio.

Provides timeline viewport math (zoom, pan, scroll, time-range calculation)
without any Qt dependency. All operations are unit-testable headless.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ViewportState:
    """Represents a timeline view state."""

    zoom_level: float = 1.0  # 1.0 = 1ms per pixel base
    scroll_x: int = 0  # offset in pixels
    view_width: int = 800  # width of visible area in pixels


def ms_to_px(ms: int, zoom_level: float) -> int:
    """Convert time (ms) to horizontal pixels."""
    return int(ms * zoom_level)


def px_to_ms(px: int, zoom_level: float) -> int:
    """Convert horizontal pixels to time (ms)."""
    if zoom_level <= 0:
        return 0
    return int(px / zoom_level)


def calculate_visible_range(state: ViewportState) -> Tuple[int, int]:
    """Calculate the visible time range [start_ms, end_ms) for current viewport."""
    start_ms = px_to_ms(state.scroll_x, state.zoom_level)
    duration_ms = px_to_ms(state.view_width, state.zoom_level)
    return start_ms, start_ms + duration_ms


def zoom_around(
    state: ViewportState, zoom_delta: float, anchor_ms: int
) -> ViewportState:
    """Calculate new scroll_x to keep anchor_ms centered or fixed during zoom."""
    old_zoom = state.zoom_level
    new_zoom = max(0.01, old_zoom * zoom_delta)

    # Calculate anchor X in current view
    anchor_x = ms_to_px(anchor_ms, old_zoom) - state.scroll_x

    # Calculate new scroll_x so anchor_ms stays at anchor_x
    new_scroll_x = ms_to_px(anchor_ms, new_zoom) - anchor_x

    return ViewportState(
        zoom_level=new_zoom,
        scroll_x=max(0, new_scroll_x),
        view_width=state.view_width,
    )


def zoom_to_fit(
    duration_ms: int, view_width: int, padding_ms: int = 1000
) -> ViewportState:
    """Calculate viewport that fits the entire timeline sequence."""
    total_duration = duration_ms + padding_ms
    new_zoom = view_width / total_duration if total_duration > 0 else 1.0
    return ViewportState(
        zoom_level=new_zoom,
        scroll_x=0,
        view_width=view_width,
    )
