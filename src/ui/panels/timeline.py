"""Timeline panel for Talib Video Studio.

Provides a multi-track graphical timeline with drag/drop, zoom, and playhead
scrubbing, styled with a Premiere Pro-inspired dark theme.
"""

from __future__ import annotations

import math
from typing import List, Dict, Optional, Tuple

from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QPoint,
    QPointF,
    QRectF,
    QMimeData,
    QLineF
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPen,
    QPainter,
    QFont,
    QFontMetrics
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QPushButton,
    QToolButton,
)

from src.ui.panels.base_panel import BasePanel
from src.core.timeline import TimelineItem as CoreItem, TimelineTrack as CoreTrack


# ------------------------------------------------------------------
# Constants & Styling
# ------------------------------------------------------------------

TRACK_HEADER_WIDTH = 120
TRACK_HEIGHT = 80
RULER_HEIGHT = 30
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0


# ------------------------------------------------------------------
# Graphical Items
# ------------------------------------------------------------------

class VisualClipItem(QGraphicsItem):
    """Graphical representation of a clip on the timeline."""

    def __init__(self, clip_data: Dict, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.clip_data = clip_data
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        # ms to px mapping (default 1ms = 0.1px)
        self.ms_to_px = 0.1
        self._update_geometry()

    def _update_geometry(self):
        self.w = self.clip_data.get('duration', 1000) * self.ms_to_px
        self.h = TRACK_HEIGHT - 10

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.w, self.h)

    def paint(self, painter: QPainter, option, widget):
        # Clip body
        color = QColor("#4a90e2") if self.isSelected() else QColor("#2c3e50")
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#34495e"), 1))
        painter.drawRoundedRect(self.boundingRect(), 4, 4)

        # Label
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Segoe UI", 8))
        name = self.clip_data.get('name', 'Clip')
        painter.drawText(8, 18, name)


class PlayheadItem(QGraphicsLineItem):
    """Vertical playhead line."""

    def __init__(self, scene_height: float):
        super().__init__(0, 0, 0, scene_height)
        pen = QPen(QColor("#e74c3c"), 2)
        self.setPen(pen)
        self.setZValue(100)


# ------------------------------------------------------------------
# Timeline Components
# ------------------------------------------------------------------

class TrackHeader(QFrame):
    """Sidebar header for a timeline track."""

    def __init__(self, name: str, track_type: str = "video"):
        super().__init__()
        self.setFixedWidth(TRACK_HEADER_WIDTH)
        self.setFixedHeight(TRACK_HEIGHT)
        self.setObjectName("panel-container")
        self.setStyleSheet(f"background-color: {'#2d2d2d' if track_type == 'video' else '#252525'}; border: 1px solid #333;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel(name)
        lbl.setStyleSheet("font-weight: bold; font-size: 10px; color: #aaa;")
        layout.addWidget(lbl)

        btns = QHBoxLayout()
        self.mute_btn = QToolButton()
        self.mute_btn.setText("M")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedSize(20, 20)

        self.lock_btn = QToolButton()
        self.lock_btn.setText("L")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setFixedSize(20, 20)

        btns.addWidget(self.mute_btn)
        btns.addWidget(self.lock_btn)
        btns.addStretch()
        layout.addLayout(btns)


class TimelinePanel(BasePanel):
    """Main Timeline Panel with multi-track layout and playhead scrubbing."""

    clip_added = Signal(dict, int, int)
    clip_moved = Signal(dict, int, int)
    clip_trimmed = Signal(dict, int, int)
    playhead_moved = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._zoom = 1.0
        self._ms_to_px = 0.1
        self._clips: List[VisualClipItem] = []

    def setup_ui(self) -> None:
        """Construct the visual timeline layout."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header/Controls
        ctrl_bar = QFrame()
        ctrl_bar.setFixedHeight(40)
        ctrl_bar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        ctrl_layout = QHBoxLayout(ctrl_bar)

        self.timecode_lbl = QLabel("00:00:00:00")
        self.timecode_lbl.setObjectName("timecode-display")
        ctrl_layout.addWidget(self.timecode_lbl)
        ctrl_layout.addStretch()

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(24, 24)
        zoom_in.clicked.connect(self._zoom_in)
        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(24, 24)
        zoom_out.clicked.connect(self._zoom_out)
        ctrl_layout.addWidget(zoom_out)
        ctrl_layout.addWidget(zoom_in)

        self.layout.addWidget(ctrl_bar)

        # Main Scrollable Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #0a0a0a; border: none;")

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Track Headers Sidebar
        self.headers_vbox = QVBoxLayout()
        self.headers_vbox.setSpacing(0)
        self.headers_vbox.setContentsMargins(0, RULER_HEIGHT, 0, 0)

        self._add_track_header("V2", "video")
        self._add_track_header("V1", "video")
        self._add_track_header("A1", "audio")
        self._add_track_header("A2", "audio")
        self.headers_vbox.addStretch()

        container_layout.addLayout(self.headers_vbox)

        # Graphics Canvas
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#1a1a1a")))

        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.view.setRenderHint(QPainter.Antialiasing)

        self.playhead = PlayheadItem(1000)
        self.scene.addItem(self.playhead)

        container_layout.addWidget(self.view)
        scroll.setWidget(container)
        self.layout.addWidget(scroll)

    def connect_signals(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_track_header(self, name: str, t_type: str):
        header = TrackHeader(name, t_type)
        self.headers_vbox.addWidget(header)

    def _zoom_in(self):
        self._set_zoom(self._zoom * 1.2)

    def _zoom_out(self):
        self._set_zoom(self._zoom / 1.2)

    def set_track_mute(self, track_index: int, muted: bool):
        """Update track mute state."""
        # Backend update
        # This will be picked up during export/stitch
        pass

    def set_track_lock(self, track_index: int, locked: bool):
        """Update track lock state."""
        # Backend update
        pass

    def add_clip_to_timeline(self, clip_data: Dict, track_index: int, position_ms: int):
        """Add a visual clip to the canvas."""
        item = VisualClipItem(clip_data)
        item.ms_to_px = self._ms_to_px * self._zoom
        item.setPos(position_ms * item.ms_to_px, track_index * TRACK_HEIGHT + 5)
        self.scene.addItem(item)
        self._clips.append(item)
        self.clip_added.emit(clip_data, track_index, position_ms)

    def razor_clip(self, item_id: str, split_ms: int):
        """Split a clip at the playhead position."""
        # Find item
        item = None
        for itm in self._clips:
            if itm.clip_data.get('id') == item_id:
                item = itm
                break
        if not item: return

        # Split visual item
        self.scene.removeItem(item)
        self._clips.remove(item)

        # Razor logic (handled in backend by TimelineManager.split_item)
        # Assuming frontend receives updated clip list, rebuild UI
        pass

    def move_clip(self, item_id: str, new_track_index: int, new_start_ms: int):
        """Move clip along timeline."""
        # Update model
        # Re-position visual item
        item = None
        for itm in self._clips:
            if itm.clip_data.get('id') == item_id:
                item = itm
                break
        if item:
            item.setPos(new_start_ms * self._ms_to_px * self._zoom, new_track_index * TRACK_HEIGHT + 5)
            item.clip_data['start'] = new_start_ms
            item.clip_data['track_index'] = new_track_index
            self.clip_moved.emit(item.clip_data, new_track_index, new_start_ms)
