"""Export Panel for Talib Video Studio.

Provides effect controls and export configuration with FFmpeg integration.
"""

from __future__ import annotations

import math
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QSlider,
    QPushButton,
    QFrame,
    QFileDialog,
    QMessageBox,
)

from src.ui.panels.base_panel import BasePanel
from src.utils.ffmpeg import FFmpegExporter, ExportWorkerThread
from src.app.project import MediaClip


class ExportPanel(BasePanel):
    """Export Panel with effect controls and export configuration."""

    export_settings_changed = Signal(dict)
    export_started = Signal()
    export_progress = Signal(float)
    export_completed = Signal(bool, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._exporter: Optional[FFmpegExporter] = None
        self._export_thread: Optional[ExportWorkerThread] = None
        self._current_settings: Dict[str, Any] = {}
        self._is_exporting = False

    def setup_ui(self) -> None:
        """Build the export panel UI with Premiere Pro-inspired dark theme."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        header = QLabel("Export Panel")
        header.setObjectName("panel-title")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: var(--panel-header-fg);")
        main_layout.addWidget(header)

        # Settings
        settings_frame = QFrame()
        settings_frame.setObjectName("panel-container")
        settings_frame.setStyleSheet("background-color: var(--bg-light); border: 1px solid var(--border-dark);")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(8, 8, 8, 8)

        # Resolution
        res_layout = QHBoxLayout()
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(["1920x1080", "1280x720", "1080x1920"])
        res_layout.addWidget(QLabel("Resolution:"))
        res_layout.addWidget(self._resolution_combo, 1)
        settings_layout.addLayout(res_layout)

        # FPS
        fps_layout = QHBoxLayout()
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(15, 60)
        self._fps_spin.setValue(30)
        fps_layout.addWidget(QLabel("FPS:"))
        fps_layout.addWidget(self._fps_spin, 1)
        settings_layout.addLayout(fps_layout)

        # Speed
        speed_layout = QHBoxLayout()
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 10)
        self._speed_slider.setValue(5)
        speed_layout.addWidget(QLabel("Speed:"))
        speed_layout.addWidget(self._speed_slider, 1)
        settings_layout.addLayout(speed_layout)

        # Volume
        vol_layout = QHBoxLayout()
        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 200)
        self._volume_slider.setValue(100)
        vol_layout.addWidget(QLabel("Volume:"))
        vol_layout.addWidget(self._volume_slider, 1)
        settings_layout.addLayout(vol_layout)

        # Export Button
        self._export_btn = QPushButton("Export Video")
        self._export_btn.setObjectName("primary-action")
        self._export_btn.clicked.connect(self._start_export)
        settings_layout.addWidget(self._export_btn)

        main_layout.addWidget(settings_frame)

        # Progress
        self._progress_frame = QFrame()
        self._progress_frame.setObjectName("panel-container")
        self._progress_frame.setStyleSheet("background-color: var(--bg-light); border: 1px solid var(--border-dark);")
        progress_layout = QVBoxLayout(self._progress_frame)
        self._progress_label = QLabel("Export Status")
        self._progress_bar = QLabel("0%")
        progress_layout.addWidget(self._progress_label)
        progress_layout.addWidget(self._progress_bar)
        main_layout.addWidget(self._progress_frame)
        self._progress_frame.setVisible(False)

    def connect_signals(self) -> None:
        pass

    def set_export_settings(self, settings: Dict[str, Any]) -> None:
        self._resolution_combo.setCurrentText(settings.get("resolution", "1920x1080"))
        self._fps_spin.setValue(settings.get("fps", 30))
        self._current_settings.update(settings)

    def _start_export(self) -> None:
        if self._is_exporting: return

        speed = self._speed_slider.value() / 5.0
        volume = self._volume_slider.value() / 100.0

        if not self._current_settings.get("input_path"):
            QMessageBox.warning(self, "Export Error", "No media file loaded.")
            return

        if not self._current_settings.get("output_path"):
            from src.ui.dialogs import show_export_dialog
            res = show_export_dialog(self._current_settings["input_path"], parent=self)
            if res: self._current_settings.update(res)
            else: return

        self._is_exporting = True
        self._export_btn.setEnabled(False)
        self._progress_frame.setVisible(True)
        self.export_started.emit()

        exporter = FFmpegExporter(self._current_settings.get("ffmpeg_path", "ffmpeg"))
        self._export_thread = ExportWorkerThread(
            exporter,
            self._current_settings["input_path"],
            self._current_settings["output_path"],
            resolution=self._resolution_combo.currentText(),
            fps=self._fps_spin.value(),
            start_sec=self._current_settings.get("start_sec"),
            duration_sec=self._current_settings.get("duration_sec"),
        )
        # Note: Speed/volume filters would be applied here in a full multi-clip implementation
        self._export_thread.finished_export.connect(self._on_export_finished)
        self._export_thread.start()

    def _on_export_finished(self, success: bool, message: str) -> None:
        self._is_exporting = False
        self._export_btn.setEnabled(True)
        self._progress_frame.setVisible(False)
        self.export_completed.emit(success, message)
        if success:
            QMessageBox.information(self, "Export Complete", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)

    def update_progress(self, progress: float) -> None:
        if self._is_exporting:
            self._progress_bar.setText(f"{progress:.0f}%")
