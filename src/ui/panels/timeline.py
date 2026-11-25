"""Timeline panel for Talib Video Studio.

Provides a multi-track graphical timeline with direct mouse drag, edge trim,
razor cuts, snapping, optional ripple, zoom and playhead scrubbing, styled
with a Premiere Pro-inspired dark theme.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPen,
    QPainter,
    QFont,
    QTransform,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QPushButton,
    QToolButton,
)

from src.ui.panels.base_panel import BasePanel
from src.core.timeline import TimelineItem as CoreItem, TimelineTrack as CoreTrack
from src.core.timecode import format_timecode
from src.core.audio import extract_waveform_peaks, peaks_to_bars
from src.core.transitions import make_transition
from src.core.undo import TimelineState, UndoStack
from src.core.timeline_ops import (
    ms_from_x,
    track_from_y,
    snap_position,
    overlapping_clip,
    resolve_move,
    resolve_trim,
    ripple_shift,
    razor_segments,
)


# ------------------------------------------------------------------
# Constants & Styling
# ------------------------------------------------------------------

TRACK_HEADER_WIDTH = 120
TRACK_HEIGHT = 80
RULER_HEIGHT = 30
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0
EDGE_ZONE_PX = 8
MIN_CLIP_WIDTH_PX = 6

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Graphical Items
# ------------------------------------------------------------------

class VisualClipItem(QGraphicsItem):
    """Graphical representation of a clip on the timeline.

    Dragging the body moves the clip; dragging either edge trims it. All
    decisions are delegated to the owning :class:`TimelinePanel`.
    """

    def __init__(
        self,
        clip_data: Dict,
        panel: Optional["TimelinePanel"] = None,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)
        self.clip_data = clip_data
        self.panel = panel
        self.ms_to_px = 0.1
        self._drag: Optional[Dict] = None
        self._preview: Optional[tuple] = None
        self.waveform: List[float] = []
        self.is_audio = False
        self.transition_in_ms = 0
        self.transition_out_ms = 0
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self._update_geometry()

    def _update_geometry(self) -> None:
        duration = int(self.clip_data.get("duration", 1000))
        self.w = max(MIN_CLIP_WIDTH_PX, duration * self.ms_to_px)
        self.h = TRACK_HEIGHT - 10

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.w, self.h)

    def paint(self, painter: QPainter, option, widget) -> None:
        color = QColor("#4a90e2") if self.isSelected() else QColor("#2c3e50")
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#34495e"), 1))
        painter.drawRoundedRect(self.boundingRect(), 4, 4)

        if self.is_audio and self.waveform:
            painter.setPen(QPen(QColor("#9ad1ff"), 1))
            for x, top, bottom in peaks_to_bars(self.waveform, self.w, self.h):
                painter.drawLine(4 + x, 18 + top, 4 + x, 18 + bottom)
        elif self.is_audio:
            painter.setPen(QPen(QColor("#7f9bb3"), 1))
            painter.drawLine(4, 18 + self.h / 2, 4 + self.w - 8, 18 + self.h / 2)

        if self.transition_in_ms > 0:
            width = min(self.w / 2, self.transition_in_ms * self.ms_to_px)
            painter.fillRect(
                QRectF(0, 0, width, self.h), QBrush(QColor(255, 255, 255, 45))
            )
        if self.transition_out_ms > 0:
            width = min(self.w / 2, self.transition_out_ms * self.ms_to_px)
            painter.fillRect(
                QRectF(self.w - width, 0, width, self.h),
                QBrush(QColor(255, 255, 255, 45)),
            )

        if self.isSelected():
            painter.setPen(QPen(QColor("#dceafc"), 2))
            painter.drawLine(3, 4, 3, int(self.h) - 4)
            painter.drawLine(int(self.w) - 3, 4, int(self.w) - 3, int(self.h) - 4)

        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(8, 18, self.clip_data.get("name", "Clip"))

    def mousePressEvent(self, event) -> None:
        panel = self.panel
        track = int(self.clip_data.get("track_index", 0))
        if (
            panel is None
            or panel.current_tool != "select"
            or panel.is_track_locked(track)
        ):
            event.ignore()
            return

        x = event.pos().x()
        if x <= EDGE_ZONE_PX:
            mode = "trim_start"
        elif x >= self.w - EDGE_ZONE_PX:
            mode = "trim_end"
        else:
            mode = "move"

        start = int(self.clip_data.get("start", 0))
        duration = int(self.clip_data.get("duration", 0))
        self._drag = {
            "mode": mode,
            "scene": event.scenePos(),
            "start": start,
            "duration": duration,
            "track": track,
            "y": self.scenePos().y(),
            "old_end": start + duration,
        }
        self._preview = None
        self._undo_before = panel.snapshot()
        self.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag is None or self.panel is None:
            return
        self.panel.apply_item_drag(self, event.scenePos() - self._drag["scene"])

    def mouseReleaseEvent(self, event) -> None:
        if self._drag is not None and self.panel is not None:
            self.panel.commit_item_drag(self)
        self._drag = None
        self._preview = None
        event.accept()


class PlayheadItem(QGraphicsLineItem):
    """Vertical playhead line."""

    def __init__(self, scene_height: float):
        super().__init__(0, 0, 0, scene_height)
        self.setPen(QPen(QColor("#e74c3c"), 2))
        self.setZValue(100)


class TimelineView(QGraphicsView):
    """Graphics view that scrubs the ruler and applies the razor tool."""

    def __init__(self, scene, panel: "TimelinePanel"):
        super().__init__(scene)
        self._panel = panel

    def mousePressEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        panel = self._panel
        scale = panel._scale()
        if panel.current_tool == "razor":
            hit = self.scene().itemAt(scene_pos, QTransform())
            if isinstance(hit, VisualClipItem):
                split_ms = ms_from_x(scene_pos.x(), scale)
                if panel.is_snap_enabled():
                    targets = [panel.get_playhead()]
                    targets += panel._snap_points(hit.clip_data.get("id"))
                    split_ms = snap_position(
                        split_ms, targets, panel._snap_threshold_ms()
                    )
                panel.razor_clip(hit.clip_data.get("id"), split_ms)
            event.accept()
            return

        hits = [
            item
            for item in self.scene().items(scene_pos)
            if isinstance(item, VisualClipItem)
        ]
        if scene_pos.y() <= RULER_HEIGHT or not hits:
            position = ms_from_x(scene_pos.x(), scale)
            if panel.is_snap_enabled():
                position = snap_position(
                    position, panel._snap_points(), panel._snap_threshold_ms()
                )
            panel.set_playhead(position, emit=True)
        super().mousePressEvent(event)


# ------------------------------------------------------------------
# Timeline Components
# ------------------------------------------------------------------

class TrackHeader(QFrame):
    """Sidebar header for a timeline track."""

    def __init__(self, name: str, track_type: str = "video"):
        super().__init__()
        self.track_type = track_type
        self.setFixedWidth(TRACK_HEADER_WIDTH)
        self.setFixedHeight(TRACK_HEIGHT)
        self.setObjectName("panel-container")
        self.setStyleSheet(
            f"background-color: {'#2d2d2d' if track_type == 'video' else '#252525'}; "
            "border: 1px solid #333;"
        )

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
    """Main timeline panel with direct clip editing and playhead scrubbing."""

    clip_added = Signal(dict, int, int)
    clip_moved = Signal(dict, int, int)
    clip_trimmed = Signal(dict, int, int)
    clip_razored = Signal(str, list)
    clip_removed = Signal(str)
    transition_added = Signal(dict)
    transition_removed = Signal(dict)
    undo_state_changed = Signal(bool, bool)
    playhead_moved = Signal(int)
    track_mute_changed = Signal(int, bool)
    track_lock_changed = Signal(int, bool)

    def __init__(self, parent: Optional[QWidget] = None):
        self._zoom = 1.0
        self._ms_to_px = 0.1
        self._clips: List[VisualClipItem] = []
        self._track_headers: List[TrackHeader] = []
        self._track_types: List[str] = []
        self._transitions: List[Dict] = []
        self._muted_tracks: set[int] = set()
        self._locked_tracks: set[int] = set()
        self._playhead_ms = 0
        self.current_tool = "select"
        self._snap_enabled = True
        self._ripple_enabled = False
        self._razor_seq = 0
        self._undo_stack = UndoStack()
        self._restoring = False
        self._batching = False
        self._waveform_cache: Dict[str, List[float]] = {}
        super().__init__(parent)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        """Construct the visual timeline layout."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        ctrl_bar = QFrame()
        ctrl_bar.setFixedHeight(40)
        ctrl_bar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        ctrl_layout = QHBoxLayout(ctrl_bar)

        self.timecode_lbl = QLabel("00:00:00:00")
        self.timecode_lbl.setObjectName("timecode-display")
        ctrl_layout.addWidget(self.timecode_lbl)
        ctrl_layout.addStretch()

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo)
        self._redo_btn = QPushButton("Redo")
        self._redo_btn.setEnabled(False)
        self._redo_btn.clicked.connect(self.redo)
        ctrl_layout.addWidget(self._undo_btn)
        ctrl_layout.addWidget(self._redo_btn)

        self._select_tool_btn = QPushButton("Select")
        self._select_tool_btn.setCheckable(True)
        self._select_tool_btn.setChecked(True)
        self._select_tool_btn.setAutoExclusive(True)
        self._select_tool_btn.clicked.connect(lambda: self.set_tool("select"))
        self._razor_tool_btn = QPushButton("Razor")
        self._razor_tool_btn.setCheckable(True)
        self._razor_tool_btn.setAutoExclusive(True)
        self._razor_tool_btn.clicked.connect(lambda: self.set_tool("razor"))
        self._snap_btn = QPushButton("Snap")
        self._snap_btn.setCheckable(True)
        self._snap_btn.setChecked(True)
        self._snap_btn.clicked.connect(self._toggle_snap)
        self._ripple_btn = QPushButton("Ripple")
        self._ripple_btn.setCheckable(True)
        self._ripple_btn.clicked.connect(self._toggle_ripple)
        self._xfade_btn = QPushButton("Xfade")
        self._xfade_btn.clicked.connect(self.add_transition_from_selection)
        for button in (
            self._select_tool_btn,
            self._razor_tool_btn,
            self._snap_btn,
            self._ripple_btn,
            self._xfade_btn,
        ):
            button.setFixedHeight(24)
            ctrl_layout.addWidget(button)

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(24, 24)
        zoom_in.clicked.connect(self._zoom_in)
        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(24, 24)
        zoom_out.clicked.connect(self._zoom_out)
        ctrl_layout.addWidget(zoom_out)
        ctrl_layout.addWidget(zoom_in)

        self.layout.addWidget(ctrl_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #0a0a0a; border: none;")

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.headers_vbox = QVBoxLayout()
        self.headers_vbox.setSpacing(0)
        self.headers_vbox.setContentsMargins(0, RULER_HEIGHT, 0, 0)

        self._add_track_header("V2", "video")
        self._add_track_header("V1", "video")
        self._add_track_header("A1", "audio")
        self._add_track_header("A2", "audio")
        self.headers_vbox.addStretch()

        container_layout.addLayout(self.headers_vbox)

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#1a1a1a")))

        self.view = TimelineView(self.scene, self)
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
    # Tools & settings
    # ------------------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        """Switch between ``select`` and ``razor`` tools."""
        if tool not in ("select", "razor"):
            return
        self.current_tool = tool
        self._select_tool_btn.setChecked(tool == "select")
        self._razor_tool_btn.setChecked(tool == "razor")
        self.view.setCursor(Qt.ArrowCursor if tool == "select" else Qt.SplitHCursor)

    def _toggle_snap(self) -> None:
        self._snap_enabled = self._snap_btn.isChecked()

    def _toggle_ripple(self) -> None:
        self._ripple_enabled = self._ripple_btn.isChecked()

    def is_snap_enabled(self) -> bool:
        return self._snap_enabled

    def is_ripple_enabled(self) -> bool:
        return self._ripple_enabled

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = bool(enabled)
        self._snap_btn.setChecked(self._snap_enabled)

    def set_ripple_enabled(self, enabled: bool) -> None:
        self._ripple_enabled = bool(enabled)
        self._ripple_btn.setChecked(self._ripple_enabled)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_track_header(self, name: str, t_type: str):
        index = len(self._track_headers)
        header = TrackHeader(name, t_type)
        self._track_types.append(t_type)
        header.mute_btn.toggled.connect(
            lambda checked, i=index: self.set_track_mute(i, checked)
        )
        header.lock_btn.toggled.connect(
            lambda checked, i=index: self.set_track_lock(i, checked)
        )
        self._track_headers.append(header)
        self.headers_vbox.addWidget(header)

    def _scale(self) -> float:
        return self._ms_to_px * self._zoom

    def _snap_threshold_ms(self) -> int:
        scale = self._scale()
        return int(EDGE_ZONE_PX / scale) if scale > 0 else 0

    def _snap_points(self, ignore_id: Optional[str] = None) -> List[int]:
        points = {0, self._playhead_ms}
        for item in self._clips:
            data = item.clip_data
            if ignore_id is not None and data.get("id") == ignore_id:
                continue
            start = int(data.get("start", 0))
            points.add(start)
            points.add(start + int(data.get("duration", 0)))
        grid_end = max(points, default=10000) + 1000
        points.update(range(0, grid_end, 1000))
        return sorted(points)

    def _item_data(self, ignore_id: Optional[str] = None) -> List[Dict]:
        return [
            item.clip_data
            for item in self._clips
            if ignore_id is None or item.clip_data.get("id") != ignore_id
        ]

    def _find_item(self, item_id: str) -> Optional[VisualClipItem]:
        return next(
            (i for i in self._clips if i.clip_data.get("id") == item_id), None
        )

    def _set_zoom(self, zoom: float):
        """Apply a bounded zoom factor and rescale placed clips."""
        self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        scale = self._scale()
        for item in self._clips:
            item.ms_to_px = scale
            item._update_geometry()
            item.setPos(
                item.clip_data.get("start", 0) * scale,
                item.clip_data.get("track_index", 0) * TRACK_HEIGHT + 5,
            )
            item.update()
        self.set_playhead(self._playhead_ms)

    def _zoom_in(self):
        self._set_zoom(self._zoom * 1.2)

    def _zoom_out(self):
        self._set_zoom(self._zoom / 1.2)

    def set_track_mute(self, track_index: int, muted: bool):
        """Update track mute state (used by export to drop muted tracks)."""
        before = self.snapshot()
        if muted:
            self._muted_tracks.add(track_index)
        else:
            self._muted_tracks.discard(track_index)
        self.track_mute_changed.emit(track_index, muted)
        self._commit("Mute track" if muted else "Unmute track", before)

    def set_track_lock(self, track_index: int, locked: bool):
        """Update track lock state (locked tracks reject clip changes)."""
        before = self.snapshot()
        if locked:
            self._locked_tracks.add(track_index)
        else:
            self._locked_tracks.discard(track_index)
        self.track_lock_changed.emit(track_index, locked)
        self._commit("Lock track" if locked else "Unlock track", before)

    def is_track_muted(self, track_index: int) -> bool:
        return track_index in self._muted_tracks

    def is_track_locked(self, track_index: int) -> bool:
        return track_index in self._locked_tracks

    def get_muted_tracks(self) -> List[int]:
        return sorted(self._muted_tracks)

    def is_audio_track(self, track_index: int) -> bool:
        """Return whether a track holds audio clips."""
        if 0 <= track_index < len(self._track_types):
            return self._track_types[track_index] == "audio"
        return False

    def get_transitions(self) -> List[Dict]:
        """Return all transitions for export."""
        return [dict(transition) for transition in self._transitions]

    def set_clip_waveform(self, item_id: str, peaks: List[float]) -> None:
        """Attach normalized waveform peaks to a clip item and repaint it."""
        item = self._find_item(item_id)
        if item is None:
            return
        item.waveform = list(peaks)
        item.update()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def snapshot(self) -> TimelineState:
        """Capture the current editable timeline state."""
        return TimelineState(
            clips=[dict(item.clip_data) for item in self._clips],
            transitions=[dict(item) for item in self._transitions],
            muted_tracks=sorted(self._muted_tracks),
            locked_tracks=sorted(self._locked_tracks),
        )

    def can_undo(self) -> bool:
        return self._undo_stack.can_undo

    def can_redo(self) -> bool:
        return self._undo_stack.can_redo

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._emit_history_state()

    def apply_state(
        self,
        state: TimelineState,
        playhead_ms: Optional[int] = None,
        reset_history: bool = True,
    ) -> None:
        """Load an external timeline state (e.g. from a project file)."""
        self._restore_state(state)
        if playhead_ms is not None:
            self.set_playhead(playhead_ms)
        if reset_history:
            self.clear_history()

    def _emit_history_state(self) -> None:
        can_undo, can_redo = self._undo_stack.can_undo, self._undo_stack.can_redo
        self._undo_btn.setEnabled(can_undo)
        self._redo_btn.setEnabled(can_redo)
        self.undo_state_changed.emit(can_undo, can_redo)

    def _commit(self, label: str, before: TimelineState) -> bool:
        """Record a completed edit if the state actually changed."""
        if self._restoring or self._batching:
            return False
        changed = self._undo_stack.push(label, before, self.snapshot())
        self._emit_history_state()
        return changed

    def undo(self) -> bool:
        """Restore the state before the most recent edit."""
        if self._restoring:
            return False
        command = self._undo_stack.undo()
        if command is None:
            self._emit_history_state()
            return False
        try:
            self._restore_state(command.before)
        except Exception:
            logger.exception("Undo failed for %s", command.label)
            self._undo_stack.redo()
            self._emit_history_state()
            return False
        logger.info("Undo: %s", command.label)
        self._emit_history_state()
        return True

    def redo(self) -> bool:
        """Reapply the most recently undone edit."""
        if self._restoring:
            return False
        command = self._undo_stack.redo()
        if command is None:
            self._emit_history_state()
            return False
        try:
            self._restore_state(command.after)
        except Exception:
            logger.exception("Redo failed for %s", command.label)
            self._undo_stack.undo()
            self._emit_history_state()
            return False
        logger.info("Redo: %s", command.label)
        self._emit_history_state()
        return True

    def _restore_state(self, state: TimelineState) -> None:
        """Rebuild visual clips/track flags from a snapshot."""
        self._restoring = True
        try:
            for item in list(self._clips):
                self.scene.removeItem(item)
            self._clips.clear()
            self._transitions = [dict(item) for item in state.transitions]
            self._muted_tracks = set(state.muted_tracks)
            self._locked_tracks = set(state.locked_tracks)
            for data in state.clips:
                self._create_clip_item(
                    dict(data),
                    int(data.get("track_index", 0)),
                    int(data.get("start", 0)),
                    emit=False,
                )
            self._sync_track_buttons()
            self._apply_transition_markers()
        finally:
            self._restoring = False

    def _sync_track_buttons(self) -> None:
        for index, header in enumerate(self._track_headers):
            header.mute_btn.blockSignals(True)
            header.lock_btn.blockSignals(True)
            header.mute_btn.setChecked(index in self._muted_tracks)
            header.lock_btn.setChecked(index in self._locked_tracks)
            header.mute_btn.blockSignals(False)
            header.lock_btn.blockSignals(False)

    def _apply_transition_markers(self) -> None:
        for item in self._clips:
            item.transition_in_ms = 0
            item.transition_out_ms = 0
            item.update()
        for transition in self._transitions:
            for item in self._clips:
                clip_id = item.clip_data.get("id")
                if clip_id == transition.get("from_id"):
                    item.transition_out_ms = int(transition.get("duration_ms", 0))
                    item.update()
                if clip_id == transition.get("to_id"):
                    item.transition_in_ms = int(transition.get("duration_ms", 0))
                    item.update()

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def add_transition(
        self,
        first_id: str,
        second_id: str,
        max_duration_ms: int = 500,
        kind: str = "crossfade",
    ) -> Optional[Dict]:
        """Create a transition between two clips on the same unlocked track."""
        first = self._find_item(first_id)
        second = self._find_item(second_id)
        if first is None or second is None or first is second:
            return None
        before = self.snapshot()
        track = int(first.clip_data.get("track_index", 0))
        if track != int(second.clip_data.get("track_index", 0)):
            return None
        if self.is_track_locked(track) or self.is_track_muted(track):
            return None

        transition = make_transition(
            first.clip_data, second.clip_data, max_duration_ms, kind
        )
        if transition is None:
            return None
        data = transition.to_dict()
        self._transitions.append(data)
        first.transition_out_ms = transition.duration_ms
        second.transition_in_ms = transition.duration_ms
        first.update()
        second.update()
        self.transition_added.emit(data)
        self._commit("Add transition", before)
        return data

    def remove_transition(self, first_id: str, second_id: str) -> Optional[Dict]:
        """Remove a transition between two clips."""
        before = self.snapshot()
        remaining: List[Dict] = []
        removed: Optional[Dict] = None
        for transition in self._transitions:
            if (
                transition.get("from_id") == first_id
                and transition.get("to_id") == second_id
            ):
                removed = transition
            else:
                remaining.append(transition)
        if removed is None:
            return None
        self._transitions = remaining
        self._apply_transition_markers()
        self.transition_removed.emit(removed)
        self._commit("Remove transition", before)
        return removed

    def remove_clip(self, item_id: str, ripple: bool = False) -> bool:
        """Delete a clip, optionally shifting later clips left (ripple delete)."""
        item = self._find_item(item_id)
        if item is None:
            return False
        track = int(item.clip_data.get("track_index", 0))
        if self.is_track_locked(track):
            return False
        before = self.snapshot()
        start = int(item.clip_data.get("start", 0))
        duration = int(item.clip_data.get("duration", 0))
        end = start + duration

        self.scene.removeItem(item)
        self._clips.remove(item)
        self._transitions = [
            t
            for t in self._transitions
            if item_id not in (t.get("from_id"), t.get("to_id"))
        ]
        if ripple:
            self._apply_ripple(end, -duration, (item_id,))
        self._apply_transition_markers()
        self.clip_removed.emit(item_id)
        self._commit("Ripple delete clip" if ripple else "Delete clip", before)
        return True

    # ------------------------------------------------------------------
    # Keyboard-driven edit actions
    # ------------------------------------------------------------------

    def selected_clip_ids(self) -> List[str]:
        """Return ids of currently selected clip items."""
        return [
            str(item.clip_data.get("id"))
            for item in self.scene.selectedItems()
            if isinstance(item, VisualClipItem) and item.clip_data.get("id")
        ]

    def _clip_id_at_playhead(self) -> Optional[str]:
        """Return the first clip spanning the playhead, if any."""
        position = self.get_playhead()
        for item in sorted(
            self._clips, key=lambda i: int(i.clip_data.get("start", 0))
        ):
            start = int(item.clip_data.get("start", 0))
            end = start + int(item.clip_data.get("duration", 0))
            if start <= position <= end:
                return str(item.clip_data.get("id"))
        return None

    def split_at_playhead(self) -> bool:
        """Razor the selected clip (or the clip under the playhead)."""
        ids = self.selected_clip_ids()
        item_id = ids[0] if ids else self._clip_id_at_playhead()
        if item_id is None:
            return False
        item = self._find_item(item_id)
        if item is None or self.is_track_locked(
            int(item.clip_data.get("track_index", 0))
        ):
            return False
        before = self.snapshot()
        self.razor_clip(item_id, self.get_playhead())
        return self.snapshot() != before

    def delete_selected(self, ripple: bool = False) -> bool:
        """Delete selected clips, optionally rippling later clips on their tracks."""
        ids = self.selected_clip_ids()
        if not ids:
            return False
        deletable: List[str] = []
        for item_id in ids:
            item = self._find_item(item_id)
            if item is None:
                continue
            if self.is_track_locked(
                int(item.clip_data.get("track_index", 0))
            ):
                continue
            deletable.append(item_id)
        if not deletable:
            return False
        before = self.snapshot()
        self._batching = True
        try:
            for item_id in deletable:
                self.remove_clip(item_id, ripple=ripple)
        finally:
            self._batching = False
        return self._commit(
            "Ripple delete clips" if ripple else "Delete clips", before
        )

    def add_transition_from_selection(self, max_duration_ms: int = 500) -> None:
        """Crossfade the selected clip with the next clip on its track."""
        selected = self.scene.selectedItems()
        selected = [i for i in selected if isinstance(i, VisualClipItem)]
        if not selected:
            return
        first = selected[0]
        track = int(first.clip_data.get("track_index", 0))
        candidates = [
            item
            for item in self._clips
            if item is not first
            and int(item.clip_data.get("track_index", 0)) == track
            and int(item.clip_data.get("start", 0))
            >= int(first.clip_data.get("start", 0))
        ]
        if not candidates:
            return
        second = min(candidates, key=lambda i: int(i.clip_data.get("start", 0)))
        self.add_transition(
            first.clip_data.get("id"),
            second.clip_data.get("id"),
            max_duration_ms,
        )

    # ------------------------------------------------------------------
    # Playhead (monitor synchronisation)
    # ------------------------------------------------------------------

    def set_playhead(self, position_ms: int, emit: bool = False) -> None:
        """Move the playhead; emit ``playhead_moved`` only for local edits."""
        self._playhead_ms = max(0, int(position_ms))
        self.playhead.setPos(self._playhead_ms * self._scale(), 0)
        self.timecode_lbl.setText(format_timecode(self._playhead_ms))
        if emit:
            self.playhead_moved.emit(self._playhead_ms)

    def get_playhead(self) -> int:
        """Return the current playhead position in milliseconds."""
        return self._playhead_ms

    # ------------------------------------------------------------------
    # Clip creation, drag, trim and razor
    # ------------------------------------------------------------------

    def _unique_clip_id(self, base: str) -> str:
        used = {item.clip_data.get("id") for item in self._clips}
        candidate = base
        while candidate in used:
            self._razor_seq += 1
            candidate = f"{base}_r{self._razor_seq}"
        return candidate

    def _create_clip_item(
        self, data: Dict, track_index: int, position_ms: int, emit: bool = True
    ) -> VisualClipItem:
        """Create and place a visual clip (also used when restoring history)."""
        item = VisualClipItem(data, self)
        item.ms_to_px = self._scale()
        item.is_audio = self.is_audio_track(track_index)
        clip_id = str(data.get("id", ""))
        waveform = self._waveform_cache.get(clip_id)
        if waveform is None and item.is_audio and data.get("path"):
            # shortcut: first 60s only, upgrade to background extraction for long files
            waveform = extract_waveform_peaks(
                data["path"], 160, duration_sec=60
            )
        if waveform is not None:
            self._waveform_cache[clip_id] = list(waveform)
            item.waveform = list(waveform)
        item.setPos(position_ms * item.ms_to_px, track_index * TRACK_HEIGHT + 5)
        self.scene.addItem(item)
        self._clips.append(item)
        if emit:
            self.clip_added.emit(data, track_index, position_ms)
        return item

    def add_clip_to_timeline(self, clip_data: Dict, track_index: int, position_ms: int):
        """Add a visual clip to the canvas, rejecting overlaps/locked tracks."""
        before = self.snapshot()
        if self.is_track_locked(track_index):
            return None
        data = dict(clip_data)
        data["start"] = position_ms
        data["track_index"] = track_index
        duration = int(data.get("duration", 1000))
        if overlapping_clip(
            self._item_data(),
            position_ms,
            position_ms + duration,
            track_index=track_index,
        ) is not None:
            return None

        item = self._create_clip_item(data, track_index, position_ms)
        self._commit("Add clip", before)
        return item

    def apply_item_drag(self, item: VisualClipItem, delta: QPointF) -> None:
        """Preview a live move/trim using the pure edit helpers."""
        drag = item._drag
        if drag is None:
            return
        scale = self._scale()
        if scale <= 0:
            return
        cid = item.clip_data.get("id")
        start, duration, track = drag["start"], drag["duration"], drag["track"]
        snap_points = self._snap_points(cid) if self.is_snap_enabled() else []
        threshold = self._snap_threshold_ms() if self.is_snap_enabled() else 0
        delta_ms = int(delta.x() / scale)

        if drag["mode"] == "move":
            target_track = track_from_y(
                drag["y"] + delta.y(), len(self._track_headers)
            )
            if self.is_track_locked(target_track):
                return
            result = resolve_move(
                start + delta_ms,
                duration,
                target_track,
                self._item_data(cid),
                snap_points,
                threshold,
                ignore_id=cid,
            )
            if result is None:
                return
            item._preview = ("move", result, duration, target_track)
            item.setPos(result * scale, target_track * TRACK_HEIGHT + 5)
            return

        edge = "start" if drag["mode"] == "trim_start" else "end"
        result = resolve_trim(
            start,
            duration,
            edge,
            delta_ms,
            track,
            self._item_data(cid),
            snap_points,
            threshold,
            ignore_id=cid,
        )
        if result is None:
            return
        new_start, new_duration = result
        item._preview = (drag["mode"], new_start, new_duration, track)
        item.clip_data["start"] = new_start
        item.clip_data["duration"] = new_duration
        item.ms_to_px = scale
        item._update_geometry()
        item.setPos(new_start * scale, track * TRACK_HEIGHT + 5)
        item.update()

    def commit_item_drag(self, item: VisualClipItem) -> None:
        """Commit the final drag preview and emit the matching signal."""
        preview = item._preview
        drag = item._drag
        if preview is None or drag is None:
            return
        mode, start, duration, track = preview
        cid = item.clip_data.get("id")
        item.clip_data["start"] = start
        item.clip_data["duration"] = duration
        item.clip_data["track_index"] = track

        if mode == "move":
            self.clip_moved.emit(item.clip_data, track, start)
            self._commit(
                "Move clip", getattr(item, "_undo_before", self.snapshot())
            )
            return

        self.clip_trimmed.emit(item.clip_data, start, start + duration)
        if self.is_ripple_enabled():
            shift = (start + duration) - drag["old_end"]
            self._apply_ripple(drag["old_end"], shift, (cid,))
        self._commit(
            "Move clip" if mode == "move" else "Trim clip",
            getattr(item, "_undo_before", self.snapshot()),
        )

    def _apply_ripple(
        self, from_ms: int, delta_ms: int, ignore_ids: tuple
    ) -> None:
        """Shift later clips when ripple is enabled."""
        for cid, new_start in ripple_shift(
            self._item_data(), from_ms, delta_ms, ignore_ids
        ):
            item = self._find_item(cid)
            if item is None:
                continue
            track = int(item.clip_data.get("track_index", 0))
            if self.is_track_locked(track):
                continue
            item.clip_data["start"] = new_start
            item.setPos(new_start * self._scale(), track * TRACK_HEIGHT + 5)
            self.clip_moved.emit(item.clip_data, track, new_start)

    def razor_clip(self, item_id: str, split_ms: int) -> None:
        """Split a clip into two distinct items at *split_ms*."""
        item = self._find_item(item_id)
        if item is None:
            return
        before = self.snapshot()
        data = dict(item.clip_data)
        track = int(data.get("track_index", 0))
        if self.is_track_locked(track):
            return

        start = int(data.get("start", 0))
        duration = int(data.get("duration", 0))
        segments = razor_segments(
            start,
            duration,
            split_ms,
            int(data.get("in_point_ms", 0)),
            int(data.get("out_point_ms", duration)),
        )
        if not segments:
            return

        self.scene.removeItem(item)
        self._clips.remove(item)
        self._transitions = [
            t
            for t in self._transitions
            if item_id not in (t.get("from_id"), t.get("to_id"))
        ]

        scale = self._scale()
        created: List[Dict] = []
        for new_start, new_duration, in_point, out_point in segments:
            segment = dict(data)
            segment["id"] = self._unique_clip_id(item_id)
            segment["start"] = new_start
            segment["duration"] = new_duration
            segment["in_point_ms"] = in_point
            segment["out_point_ms"] = out_point
            new_item = VisualClipItem(segment, self)
            new_item.ms_to_px = scale
            new_item.is_audio = item.is_audio
            new_item.waveform = list(item.waveform)
            new_item.setPos(new_start * scale, track * TRACK_HEIGHT + 5)
            self.scene.addItem(new_item)
            self._clips.append(new_item)
            created.append(segment)

        self.clip_razored.emit(item_id, created)
        self._commit("Razor clip", before)

    def move_clip(self, item_id: str, new_track_index: int, new_start_ms: int):
        """Move clip along timeline (public API, used by non-mouse callers)."""
        if self.is_track_locked(new_track_index):
            return
        item = self._find_item(item_id)
        if item is None:
            return
        before = self.snapshot()
        scale = self._scale()
        item.setPos(new_start_ms * scale, new_track_index * TRACK_HEIGHT + 5)
        item.clip_data["start"] = new_start_ms
        item.clip_data["track_index"] = new_track_index
        self.clip_moved.emit(item.clip_data, new_track_index, new_start_ms)
        self._commit("Move clip", before)
