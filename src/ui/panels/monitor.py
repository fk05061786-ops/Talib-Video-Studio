"""Monitor panel for Talib Video Studio.

Provides Source and Program monitor functionality with playback controls
and trim markers using Premiere Pro-inspired dark theme.
"""

from __future__ import annotations

import math
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QFrame,
)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

from src.ui.panels.base_panel import BasePanel
from src.core.media import get_media_duration, extract_frame


class MonitorPanel(BasePanel):
    """Monitor panel with source/program views and playback controls.

    Emits ``in_point_set`` when In point is set, ``out_point_set`` when
    Out point is set, and ``playhead_position`` during scrubbing.
    """

    in_point_set = Signal(int)
    out_point_set = Signal(int)
    playhead_position = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._source_player: Optional[QMediaPlayer] = None
        self._program_player: Optional[QMediaPlayer] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._is_scrubbing = False
        self._in_point: Optional[int] = None
        self._out_point: Optional[int] = None
        self._last_position = 0

    def setup_ui(self) -> None:
        """Build the monitor panel UI with Premiere Pro-inspired dark theme.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Header - styled
        header = QLabel("Monitor")
        header.setObjectName("panel-title")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: var(--panel-header-fg);")
        main_layout.addWidget(header)

        # Split view container
        split_container = QWidget()
        split_container.setObjectName("panel-container")
        split_layout = QHBoxLayout(split_container)
        split_layout.setContentsMargins(0, 0, 0, 0)

        # Source monitor
        self._source_frame = QFrame()
        self._source_frame.setObjectName("panel-container")
        self._source_frame.setStyleSheet("background-color: var(--bg-dark); border: 1px solid var(--border-dark);")
        source_layout = QVBoxLayout(self._source_frame)
        source_layout.setContentsMargins(4, 4, 4, 4)
        self._source_label = QLabel("Source Monitor")
        self._source_label.setAlignment(Qt.AlignCenter)
        self._source_label.setStyleSheet("color: var(--text-secondary); font-size: 12px;")
        source_layout.addWidget(self._source_label)
        split_layout.addWidget(self._source_frame, 1)

        # Program monitor
        self._program_frame = QFrame()
        self._program_frame.setObjectName("panel-container")
        self._program_frame.setStyleSheet("background-color: var(--bg-dark); border: 1px solid var(--border-dark);")
        program_layout = QVBoxLayout(self._program_frame)
        program_layout.setContentsMargins(4, 4, 4, 4)
        self._program_label = QLabel("Program Monitor")
        self._program_label.setAlignment(Qt.AlignCenter)
        self._program_label.setStyleSheet("color: var(--text-secondary); font-size: 12px;")
        program_layout.addWidget(self._program_label)
        split_layout.addWidget(self._program_frame, 1)

        main_layout.addWidget(split_container, 2)

        # Controls area
        controls_frame = QFrame()
        controls_frame.setObjectName("panel-container")
        controls_frame.setStyleSheet("background-color: var(--bg-mid); border: 1px solid var(--border-dark);")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(8, 8, 8, 8)

        # Timecode display
        time_layout = QHBoxLayout()
        self._timecode_label = QLabel("00:00:00")
        self._timecode_label.setObjectName("timecode-display")
        self._timecode_label.setStyleSheet("background-color: var(--timecode-bg); border: 1px solid var(--border-dark); color: var(--timecode-fg); font-family: 'Courier New', 'Courier', monospace; font-size: 14px; padding: 4px 8px; border-radius: 4px;")
        time_layout.addWidget(self._timecode_label)
        time_layout.addStretch(1)
        controls_layout.addLayout(time_layout)

        # Scrubber
        self._scrubber = QSlider(Qt.Horizontal)
        self._scrubber.setRange(0, 10000)
        self._scrubber.setTickPosition(QSlider.TicksBelow)
        self._scrubber.setTickInterval(1000)
        self._scrubber.valueChanged.connect(self._on_scrub)
        self._scrubber.setStyleSheet("QSlider::groove:horizontal { height: 6px; background-color: var(--bg-light); border: 1px solid var(--border-mid); margin: 8px 0; } QSlider::handle:horizontal { width: 16px; height: 16px; background-color: var(--accent-blue); border: 2px solid var(--bg-mid); margin: -6px 0; border-radius: 50%; } QSlider::handle:horizontal:hover { background-color: #5d9cec; }")
        controls_layout.addWidget(self._scrubber)

        # Trim controls
        trim_layout = QHBoxLayout()
        self._set_in_btn = QPushButton("Set In")
        self._set_in_btn.setObjectName("primary-action")
        self._set_in_btn.clicked.connect(self._set_in_point)
        self._set_out_btn = QPushButton("Set Out")
        self._set_out_btn.setObjectName("primary-action")
        self._set_out_btn.clicked.connect(self._set_out_point)
        self._clear_trim_btn = QPushButton("Clear Trim")
        self._clear_trim_btn.clicked.connect(self._clear_trim)
        trim_layout.addWidget(self._set_in_btn)
        trim_layout.addWidget(self._set_out_btn)
        trim_layout.addWidget(self._clear_trim_btn)
        controls_layout.addLayout(trim_layout)

        # Playback controls
        play_layout = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self._toggle_play)
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._stop)
        play_layout.addWidget(self._play_btn)
        play_layout.addWidget(self._pause_btn)
        play_layout.addWidget(self._stop_btn)
        controls_layout.addLayout(play_layout)

        main_layout.addWidget(controls_frame)

    def connect_signals(self) -> None:
        """Wire up internal signals.
        """
        # Connect to timeline for playhead sync
        pass

    def set_source_media(self, path: str) -> None:
        """Load source media into the source monitor.
        """
        if self._source_player is None:
            self._source_player = QMediaPlayer()
        self._source_player.setSource(QUrl.fromLocalFile(path))
        # Get duration for scrubber range
        duration = get_media_duration(path)
        if duration:
            self._scrubber.setRange(0, int(duration * 1000))

    def _on_scrub(self, position: int) -> None:
        """Handle scrubber movement.
        """
        self._is_scrubbing = True
        self._last_position = position
        self.playhead_position.emit(position)
        # Update timecode
        secs = position / 1000.0
        timecode = f"{int(secs)//3600:02d}:{int(secs)%3600//60:02d}:{int(secs)%60:02d}.{int(secs*1000)%1000:03d}"
        self._timecode_label.setText(timecode)
        QTimer.singleShot(100, self._update_scrub_position)

    def _update_scrub_position(self) -> None:
        """Update actual player position based on scrub.
        """
        if not self._is_scrubbing:
            return
        self._is_scrubbing = False

    def _set_in_point(self) -> None:
        """Set In point at current scrubber position.
        """
        position = self._scrubber.value()
        self._in_point = position
        self.in_point_set.emit(position)

    def _set_out_point(self) -> None:
        """Set Out point at current scrubber position.
        """
        position = self._scrubber.value()
        if self._in_point and position > self._in_point:
            self._out_point = position
            self.out_point_set.emit(position)

    def _clear_trim(self) -> None:
        """Clear trim points.
        """
        self._in_point = None
        self._out_point = None