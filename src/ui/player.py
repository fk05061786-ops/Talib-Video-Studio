"""VideoPlayerWidget for Talib Video Studio.

A QWidget-based media player with playback controls, timeline, and trim functionality.
Uses PySide6's QMediaPlayer/QVideoWidget for video playback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import (
    Qt,
    Signal,
    QTimer,
    QUrl,
    QTime,
    QPointF,
    QEvent,
)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QFrame,
    QSizePolicy,
)


class VideoPlayerWidget(QWidget):
    """Video player widget with playback controls, timeline, and trim functionality.

    Parameters
    ----------
    parent: QWidget | None, optional
        Parent widget.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._media_player: Optional[QMediaPlayer] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._setup_ui()
        self._setup_signals()
        self._setup_player()
        self._trim_in = 0
        self._trim_out = 0
        self._trim_status = "No trim"
        self._media_path: Optional[Path] = None
        self._is_playing = False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the player UI layout.

        Structure:
          - Top: Play/Pause/Stop buttons
          - Middle: Video widget + timeline slider
          - Bottom: Time labels + trim controls
        """
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Top controls
        top_controls = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("play_btn")
        self.play_btn.clicked.connect(self._toggle_play)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("pause_btn")
        self.pause_btn.clicked.connect(self._toggle_pause)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.clicked.connect(self._stop)

        top_controls.addWidget(self.play_btn)
        top_controls.addWidget(self.pause_btn)
        top_controls.addWidget(self.stop_btn)
        main_layout.addLayout(top_controls)

        # Middle: Video widget + timeline slider
        middle_layout = QHBoxLayout()
        self._video_widget = QVideoWidget()
        self._video_widget.setObjectName("video_widget")
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        middle_layout.addWidget(self._video_widget)

        self._timeline_slider = QSlider(Qt.Horizontal)
        self._timeline_slider.setObjectName("timeline_slider")
        self._timeline_slider.setRange(0, 0)
        self._timeline_slider.setValue(0)
        self._timeline_slider.setTickPosition(QSlider.TicksBelow)
        self._timeline_slider.setTickInterval(10)
        middle_layout.addWidget(self._timeline_slider)
        main_layout.addLayout(middle_layout)

        # Bottom: Time labels + trim controls
        bottom_layout = QHBoxLayout()
        self._current_time = QLabel("00:00")
        self._current_time.setObjectName("current_time")
        bottom_layout.addWidget(self._current_time)

        self._total_time = QLabel("00:00")
        self._total_time.setObjectName("total_time")
        bottom_layout.addWidget(self._total_time)

        self._trim_status = QLabel("No trim")
        self._trim_status.setObjectName("trim_status")
        bottom_layout.addWidget(self._trim_status)

        self._set_in_btn = QPushButton("Set In")
        self._set_in_btn.setObjectName("set_in_btn")
        self._set_in_btn.clicked.connect(self._set_trim_in)
        bottom_layout.addWidget(self._set_in_btn)

        self._set_out_btn = QPushButton("Set Out")
        self._set_out_btn.setObjectName("set_out_btn")
        self._set_out_btn.clicked.connect(self._set_trim_out)
        bottom_layout.addWidget(self._set_out_btn)

        main_layout.addLayout(bottom_layout)

    # ------------------------------------------------------------------
    # Player setup
    # ------------------------------------------------------------------

    def _setup_player(self) -> None:
        """Initialize QMediaPlayer and QAudioOutput."""
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setVideoOutput(self._video_widget)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _setup_signals(self) -> None:
        """Connect media player signals to UI."""
        self._media_player.positionChanged.connect(self._update_time_labels)
        self._media_player.durationChanged.connect(self._update_slider_range)
        self._media_player.stateChanged.connect(self._handle_state_changed)
        self._timeline_slider.valueChanged.connect(self._seek)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_media(self, path: Path) -> None:
        """Load media file into the player.

        Parameters
        ----------
        path: Path
            Path to the media file.
        """
        self._media_path = path
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()
        self._is_playing = True
        self._update_time_labels()

    def set_trim_in(self, position: int) -> None:
        """Set the trim in position.

        Parameters
        ----------
        position: int
            Position in milliseconds.
        """
        self._trim_in = position
        self._update_trim_status()

    def set_trim_out(self, position: int) -> None:
        """Set the trim out position.

        Parameters
        ----------
        position: int
            Position in milliseconds.
        """
        self._trim_out = position
        self._update_trim_status()

    def get_trim_range(self) -> Tuple[int, int]:
        """Get the current trim range.

        Returns
        -------
        tuple[int, int]
            (trim_in, trim_out) in milliseconds.
        """
        return self._trim_in, self._trim_out

    # ------------------------------------------------------------------
    # Playback control helpers
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        """Toggle playback."""
        if self._media_player.state() == QMediaPlayer.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()

    def _toggle_pause(self) -> None:
        """Pause playback."""
        self._media_player.pause()

    def _stop(self) -> None:
        """Stop playback and reset player."""
        self._media_player.stop()
        self._is_playing = False
        self._update_time_labels()

    def _seek(self, position: int) -> None:
        """Seek to a position.

        Parameters
        ----------
        position: int
            Position in milliseconds.
        """
        self._media_player.setPosition(position)

    # ------------------------------------------------------------------
    # Time label updates
    # ------------------------------------------------------------------

    def _update_time_labels(self) -> None:
        """Update current/total time labels."""
        position = self._media_player.position()
        duration = self._media_player.duration()

        current_time = QTime(0, 0).addMSecs(position)
        total_time = QTime(0, 0).addMSecs(duration)

        self._current_time.setText(current_time.toString("mm:ss"))
        self._total_time.setText(total_time.toString("mm:ss"))

    def _update_slider_range(self, duration: int) -> None:
        """Update the timeline slider range."""
        self._timeline_slider.setRange(0, duration)

    # ------------------------------------------------------------------
    # Trim status updates
    # ------------------------------------------------------------------

    def _update_trim_status(self) -> None:
        """Update the trim status label."""
        if self._trim_in == 0 and self._trim_out == 0:
            self._trim_status.setText("No trim")
        else:
            self._trim_status.setText(f"Trim: {self._trim_in}ms–{self._trim_out}ms")

    # ------------------------------------------------------------------
    # State handling
    # ------------------------------------------------------------------

    def _handle_state_changed(self, state: int) -> None:
        """Handle media player state changes.

        Parameters
        ----------
        state: int
            QMediaPlayer state.
        """
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("Pause")
            self.pause_btn.setText("Play")
            self._is_playing = True
        elif state == QMediaPlayer.PausedState:
            self.play_btn.setText("Play")
            self.pause_btn.setText("Pause")
            self._is_playing = False
        elif state == QMediaPlayer.StoppedState:
            self.play_btn.setText("Play")
            self.pause_btn.setText("Pause")
            self._is_playing = False
            self._update_time_labels()