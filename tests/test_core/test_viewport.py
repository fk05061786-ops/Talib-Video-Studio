"""Headless tests for viewport geometry."""

import unittest
from src.core.viewport import (
    ViewportState,
    ms_to_px,
    px_to_ms,
    calculate_visible_range,
    zoom_around,
    zoom_to_fit,
)

class TestViewport(unittest.TestCase):
    def test_conversions(self):
        self.assertEqual(ms_to_px(1000, 1.0), 1000)
        self.assertEqual(ms_to_px(1000, 0.5), 500)
        self.assertEqual(px_to_ms(500, 0.5), 1000)
        self.assertEqual(px_to_ms(0, 1.0), 0)
        self.assertEqual(px_to_ms(100, 0.0), 0)

    def test_visible_range(self):
        state = ViewportState(zoom_level=0.1, scroll_x=100, view_width=500)
        # scroll_x=100 -> start_ms=1000
        # view_width=500 -> duration_ms=5000
        start, end = calculate_visible_range(state)
        self.assertEqual(start, 1000)
        self.assertEqual(end, 6000)

    def test_zoom_around(self):
        state = ViewportState(zoom_level=1.0, scroll_x=0, view_width=800)
        # Zoom in 2x around time=100ms
        # At zoom=1.0, 100ms is at x=100
        new_state = zoom_around(state, 2.0, 100)
        self.assertEqual(new_state.zoom_level, 2.0)
        # 100ms at zoom=2.0 is x=200
        # To keep it at x=100, scroll_x must be 100
        self.assertEqual(new_state.scroll_x, 100)

    def test_zoom_to_fit(self):
        # 10s duration (10000ms) + 1s padding = 11000ms
        # 1100px view width
        state = zoom_to_fit(10000, 1100, padding_ms=1000)
        self.assertEqual(state.zoom_level, 0.1)
        self.assertEqual(state.scroll_x, 0)

if __name__ == "__main__":
    unittest.main()
