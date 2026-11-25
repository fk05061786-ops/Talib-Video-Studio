"""Monitor panel for Talib Video Studio.

Provides Source and Program monitor switching, playback, frame-accurate
stepping, scrubbing, and timecode/In-Out overlays using a Premiere
Pro-inspired dark theme.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from src.ui.panels.base_panel import BasePanel
from src.core.media import get_media_info
from src.core.timecode import format_timecode, step_position

NO_TIMECODE = "--:--:--:--"


class MonitorPanel(BasePanel):
    """Monitor panel with source/program views and playback controls.

    Emits ``in_point_set`` when In point is set, ``out_point_set`` when
    Out point is set, ``playhead_position`` when the viewed position changes,
    and ``monitor_switched`` when Source/Program is switched.
    """

    in_point_set = Signal(int)
    out_point_set = Signal(int)
    playhead_position = Signal(int)
    monitor_switched = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        self._source_player: Optional[QMediaPlayer] = None
        self._program_player: Optional[QMediaPlayer] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._is_scrubbing = False
        self._in_point: Optional[int] = None
        self._out_point: Optional[int] = None
        self._last_position = 0
        self._active_monitor = "source"
        self._fps = 30.0
        self._source_path: Optional[str] = None
        self._program_path: Optional[str] = None
        super().__init__(parent)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        """Build the monitor panel UI with Premiere Pro-inspired dark theme."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Header + Source/Program switch
        header_layout = QHBoxLayout()
        header = QLabel("Monitor")
        header.setObjectName("panel-title")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: var(--panel-header-fg);")
        header_layout.addWidget(header)
        header_layout.addStretch(1)

        self._source_tab_btn = QPushButton("Source")
        self._source_tab_btn.setObjectName("primary-action")
        self._source_tab_btn.setCheckable(True)
        self._source_tab_btn.setChecked(True)
        self._source_tab_btn.clicked.connect(
            lambda _checked: self.set_active_monitor("source")
        )
        self._program_tab_btn = QPushButton("Program")
        self._program_tab_btn.setObjectName("primary-action")
        self._program_tab_btn.setCheckable(True)
        self._program_tab_btn.clicked.connect(
            lambda _checked: self.set_active_monitor("program")
        )
        header_layout.addWidget(self._source_tab_btn)
        header_layout.addWidget(self._program_tab_btn)
        main_layout.addLayout(header_layout)

        # Split view container
        split_container = QWidget()
        split_container.setObjectName("panel-container")
        split_layout = QHBoxLayout(split_container)
        split_layout.setContentsMargins(0, 0, 0, 0)

        # Source monitor
        self._source_frame = QFrame()
        self._source_frame.setObjectName("panel-container")
        self._source_frame.setStyleSheet(
            "background-color: var(--bg-dark); border: 2px solid #4a90e2;"
        )
        source_layout = QVBoxLayout(self._source_frame)
        source_layout.setContentsMargins(4, 4, 4, 4)
        self._source_label = QLabel("Source Monitor")
        self._source_label.setAlignment(Qt.AlignCenter)
        self._source_label.setStyleSheet("color: var(--text-secondary); font-size: 12px;")
        source_layout.addWidget(self._source_label)
        self._source_video = QVideoWidget()
        self._source_video.setMinimumHeight(160)
        source_layout.addWidget(self._source_video, 1)
        self._source_overlay = self._make_overlay(self._source_video, "SOURCE")
        split_layout.addWidget(self._source_frame, 1)

        # Program monitor
        self._program_frame = QFrame()
        self._program_frame.setObjectName("panel-container")
        self._program_frame.setStyleSheet(
            "background-color: var(--bg-dark); border: 2px solid #333;"
        )
        program_layout = QVBoxLayout(self._program_frame)
        program_layout.setContentsMargins(4, 4, 4, 4)
        self._program_label = QLabel("Program Monitor")
        self._program_label.setAlignment(Qt.AlignCenter)
        self._program_label.setStyleSheet("color: var(--text-secondary); font-size: 12px;")
        program_layout.addWidget(self._program_label)
        self._program_video = QVideoWidget()
        self._program_video.setMinimumHeight(160)
        program_layout.addWidget(self._program_video, 1)
        self._program_overlay = self._make_overlay(self._program_video, "PROGRAM")
        split_layout.addWidget(self._program_frame, 1)

        main_layout.addWidget(split_container, 2)

        # Controls area
        controls_frame = QFrame()
        controls_frame.setObjectName("panel-container")
        controls_frame.setStyleSheet(
            "background-color: var(--bg-mid); border: 1px solid var(--border-dark);"
        )
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(8, 8, 8, 8)

        # Timecode + In/Out readout
        time_layout = QHBoxLayout()
        self._timecode_label = QLabel("00:00:00:00")
        self._timecode_label.setObjectName("timecode-display")
        self._timecode_label.setStyleSheet(
            "background-color: var(--timecode-bg); border: 1px solid var(--border-dark); "
            "color: var(--timecode-fg); font-family: 'Courier New', 'Courier', monospace; "
            "font-size: 14px; padding: 4px 8px; border-radius: 4px;"
        )
        time_layout.addWidget(self._timecode_label)
        self._in_out_label = QLabel(f"In: {NO_TIMECODE}   Out: {NO_TIMECODE}")
        self._in_out_label.setObjectName("in-out-display")
        self._in_out_label.setStyleSheet("color: var(--text-secondary); font-size: 11px;")
        time_layout.addWidget(self._in_out_label)
        time_layout.addStretch(1)
        controls_layout.addLayout(time_layout)

        # Scrubber
        self._scrubber = QSlider(Qt.Horizontal)
        self._scrubber.setRange(0, 10000)
        self._scrubber.setTickPosition(QSlider.TicksBelow)
        self._scrubber.setTickInterval(1000)
        self._scrubber.valueChanged.connect(self._on_scrub)
        self._scrubber.setStyleSheet(
            "QSlider::groove:horizontal { height: 6px; background-color: var(--bg-light); "
            "border: 1px solid var(--border-mid); margin: 8px 0; } "
            "QSlider::handle:horizontal { width: 16px; height: 16px; "
            "background-color: var(--accent-blue); border: 2px solid var(--bg-mid); "
            "margin: -6px 0; border-radius: 50%; } "
            "QSlider::handle:horizontal:hover { background-color: #5d9cec; }"
        )
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

        # Playback + frame stepping controls
        play_layout = QHBoxLayout()
        self._step_back_btn = QPushButton("< Frame")
        self._step_back_btn.clicked.connect(lambda: self.step_frame(-1))
        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self._toggle_play)
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._stop)
        self._step_fwd_btn = QPushButton("Frame >")
        self._step_fwd_btn.clicked.connect(lambda: self.step_frame(1))
        play_layout.addWidget(self._step_back_btn)
        play_layout.addWidget(self._play_btn)
        play_layout.addWidget(self._pause_btn)
        play_layout.addWidget(self._stop_btn)
        play_layout.addWidget(self._step_fwd_btn)
        controls_layout.addLayout(play_layout)

        main_layout.addWidget(controls_frame)

    @staticmethod
    def _make_overlay(video_widget: QVideoWidget, title: str) -> QLabel:
        """Create a timecode overlay as a child of a video widget."""
        overlay = QLabel(video_widget)
        overlay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        overlay.setStyleSheet(
            "color: #e0e0e0; background-color: rgba(0, 0, 0, 140); "
            "font-family: 'Courier New', monospace; font-size: 10px; padding: 2px;"
        )
        overlay.setText(f"{title}\n{NO_TIMECODE}")
        overlay.setGeometry(4, 4, max(0, video_widget.width() - 8), 56)
        overlay.raise_()
        return overlay

    def resizeEvent(self, event) -> None:
        """Keep overlays sized to their video widgets."""
        super().resizeEvent(event)
        if not hasattr(self, "_source_overlay"):
            return
        for overlay, video in (
            (self._source_overlay, self._source_video),
            (self._program_overlay, self._program_video),
        ):
            overlay.setGeometry(4, 4, max(0, video.width() - 8), 56)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def connect_signals(self) -> None:
        """Create players and wire playback/scrub signals for both monitors."""
        self._source_player = QMediaPlayer()
        self._source_audio = QAudioOutput()
        self._source_player.setAudioOutput(self._source_audio)
        self._source_player.setVideoOutput(self._source_video)

        self._program_player = QMediaPlayer()
        self._program_audio = QAudioOutput()
        self._program_player.setAudioOutput(self._program_audio)
        self._program_player.setVideoOutput(self._program_video)

        for player in (self._source_player, self._program_player):
            player.positionChanged.connect(
                lambda pos, p=player: self._on_player_position(p, pos)
            )
            player.durationChanged.connect(
                lambda dur, p=player: self._on_player_duration(p, dur)
            )
            if hasattr(player, "playbackStateChanged"):
                player.playbackStateChanged.connect(
                    lambda state, p=player: self._on_player_state(p, state)
                )
            elif hasattr(player, "stateChanged"):
                player.stateChanged.connect(
                    lambda state, p=player: self._on_player_state(p, state)
                )

    # ------------------------------------------------------------------
    # Source / Program switching
    # ------------------------------------------------------------------

    def active_player(self) -> Optional[QMediaPlayer]:
        """Return the player for the currently active monitor."""
        return self._source_player if self._active_monitor == "source" else self._program_player

    def set_active_monitor(self, which: str) -> None:
        """Switch the active monitor between ``"source"`` and ``"program"``."""
        if which not in ("source", "program"):
            return
        self._active_monitor = which
        self._source_tab_btn.setChecked(which == "source")
        self._program_tab_btn.setChecked(which == "program")

        active = self.active_player()
        for player in (self._source_player, self._program_player):
            if player is not None and player is not active:
                player.pause()

        for frame, is_active in (
            (self._source_frame, which == "source"),
            (self._program_frame, which == "program"),
        ):
            border = "#4a90e2" if is_active else "#333"
            frame.setStyleSheet(
                f"background-color: var(--bg-dark); border: 2px solid {border};"
            )

        if active is not None:
            self._set_scrubber(maximum=max(0, active.duration()), value=active.position())
            self._update_timecode(active.position())
        self.monitor_switched.emit(which)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_fps(self, fps: float) -> None:
        """Set the frame rate used for timecode and frame stepping."""
        try:
            value = float(fps)
        except (TypeError, ValueError):
            value = 30.0
        self._fps = value if value > 0 else 30.0
        self._update_timecode(self._last_position)

    def set_source_media(self, path: str) -> None:
        """Load source media into the source monitor and select it."""
        self._source_path = str(path)
        self._source_player.setSource(QUrl.fromLocalFile(self._source_path))
        info = get_media_info(self._source_path)
        self.set_fps(info.get("fps", 30.0))
        duration = info.get("duration", 0.0)
        if duration:
            self._set_scrubber(maximum=int(duration * 1000), value=0)
        self._in_point = None
        self._out_point = None
        self.set_active_monitor("source")
        self._update_timecode(0)

    def set_program_media(self, path: str) -> None:
        """Load program media into the program monitor and select it."""
        self._program_path = str(path)
        self._program_player.setSource(QUrl.fromLocalFile(self._program_path))
        info = get_media_info(self._program_path)
        self.set_fps(info.get("fps", 30.0))
        duration = info.get("duration", 0.0)
        if duration:
            self._set_scrubber(maximum=int(duration * 1000), value=0)
        self.set_active_monitor("program")
        self._update_timecode(0)

    def step_frame(self, delta_frames: int) -> None:
        """Move one or more frames forward/backward on the active monitor."""
        player = self.active_player()
        if player is None:
            return
        target = step_position(
            player.position(), delta_frames, self._fps, player.duration()
        )
        player.pause()
        player.setPosition(target)
        self._set_scrubber(value=target)
        self._update_timecode(target)
        self.playhead_position.emit(target)

    def set_position(self, position_ms: int) -> None:
        """Seek the active monitor from an external playhead (no echo emit)."""
        position = max(0, int(position_ms))
        self._last_position = position
        self._set_scrubber(value=position)
        self._update_timecode(position)
        player = self.active_player()
        if player is not None and player.position() != position:
            player.setPosition(position)

    def stop_all(self) -> None:
        """Stop both players (used during shutdown)."""
        for player in (self._source_player, self._program_player):
            if player is not None:
                player.stop()

    def play_pause(self) -> None:
        """Public toggle used by keyboard shortcuts."""
        self._toggle_play()

    def previous_frame(self) -> None:
        """Step one frame backward."""
        self.step_frame(-1)

    def next_frame(self) -> None:
        """Step one frame forward."""
        self.step_frame(1)

    def set_in(self) -> None:
        """Public In-point action used by keyboard shortcuts."""
        self._set_in_point()

    def set_out(self) -> None:
        """Public Out-point action used by keyboard shortcuts."""
        self._set_out_point()

    def clear_trim(self) -> None:
        """Public clear-trim action used by keyboard shortcuts."""
        self._clear_trim()

    # ------------------------------------------------------------------
    # Player signal handlers
    # ------------------------------------------------------------------

    def _on_player_position(self, player: QMediaPlayer, position: int) -> None:
        """Reflect playback position and publish it to the timeline."""
        if player is not self.active_player() or self._is_scrubbing:
            return
        self._last_position = position
        self._set_scrubber(value=position)
        self._update_timecode(position)
        self.playhead_position.emit(position)

    def _on_player_duration(self, player: QMediaPlayer, duration: int) -> None:
        """Keep the scrubber range in sync with the active media."""
        if player is not self.active_player():
            return
        if duration > 0:
            self._set_scrubber(maximum=duration)
        self._update_timecode(player.position())

    def _on_player_state(self, player: QMediaPlayer, state: int) -> None:
        """Reflect playback state on the Play button."""
        if player is not self.active_player():
            return
        self._play_btn.setText("Pause" if state == QMediaPlayer.PlayingState else "Play")

    # ------------------------------------------------------------------
    # Playback control helpers
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        """Play or pause the active monitor."""
        player = self.active_player()
        if player is None:
            return
        state = (
            player.playbackState()
            if hasattr(player, "playbackState")
            else player.state()
        )
        if state == QMediaPlayer.PlayingState:
            player.pause()
        else:
            player.play()

    def _toggle_pause(self) -> None:
        """Pause the active monitor."""
        player = self.active_player()
        if player is not None:
            player.pause()

    def _stop(self) -> None:
        """Stop the active monitor."""
        player = self.active_player()
        if player is not None:
            player.stop()

    # ------------------------------------------------------------------
    # Scrubbing
    # ------------------------------------------------------------------

    def _set_scrubber(
        self, value: Optional[int] = None, maximum: Optional[int] = None
    ) -> None:
        """Update the scrubber programmatically without retriggering scrub."""
        self._scrubber.blockSignals(True)
        if maximum is not None:
            self._scrubber.setRange(0, maximum)
        if value is not None:
            self._scrubber.setValue(value)
        self._scrubber.blockSignals(False)

    def _on_scrub(self, position: int) -> None:
        """Handle scrubber movement."""
        self._is_scrubbing = True
        self._last_position = position
        self._update_timecode(position)
        self.playhead_position.emit(position)
        QTimer.singleShot(100, self._update_scrub_position)

    def _update_scrub_position(self) -> None:
        """Seek the active player after a scrub gesture settles."""
        if not self._is_scrubbing:
            return
        self._is_scrubbing = False
        player = self.active_player()
        if player is not None:
            player.setPosition(self._last_position)

    # ------------------------------------------------------------------
    # Timecode / In-Out display
    # ------------------------------------------------------------------

    def _update_timecode(self, position: int) -> None:
        """Refresh timecode labels and both monitor overlays."""
        timecode = format_timecode(position, self._fps)
        in_tc = (
            format_timecode(self._in_point, self._fps)
            if self._in_point is not None
            else NO_TIMECODE
        )
        out_tc = (
            format_timecode(self._out_point, self._fps)
            if self._out_point is not None
            else NO_TIMECODE
        )
        self._timecode_label.setText(timecode)
        self._in_out_label.setText(f"In: {in_tc}   Out: {out_tc}")
        for overlay, title in (
            (self._source_overlay, "SOURCE"),
            (self._program_overlay, "PROGRAM"),
        ):
            overlay.setText(f"{title}\n{timecode}\nIn {in_tc}  Out {out_tc}")

    def _set_in_point(self) -> None:
        """Set In point at the current position."""
        position = self._scrubber.value()
        self._in_point = position
        self.in_point_set.emit(position)
        self._update_timecode(position)

    def _set_out_point(self) -> None:
        """Set Out point at the current position, after In."""
        position = self._scrubber.value()
        if self._in_point is not None and position > self._in_point:
            self._out_point = position
            self.out_point_set.emit(position)
            self._update_timecode(position)

    def _clear_trim(self) -> None:
        """Clear trim points."""
        self._in_point = None
        self._out_point = None
        self._update_timecode(self._scrubber.value())
