"""MainWindow for Talib Video Studio.

Provides the central application window with a dark-themed UI, action bar,
video player viewport, and status bar. Designed so Parts 2–4 can plug in
via clear method hooks without rewriting the window structure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStatusBar,
    QFrame,
    QSplitter,
    QTabWidget,
    QStackedWidget,
    QDockWidget,
)

from .dialogs import show_import_dialog, show_export_dialog
from .utils.ffmpeg import ExportWorkerThread
from .panels import MediaBinPanel, MonitorPanel, TimelinePanel, ExportPanel
from src.app.session import Session
import sys


class MainWindow(QMainWindow):
    """Main application window for Talib Video Studio.

    Parameters
    ----------
    config: dict | None, optional
        Configuration dictionary. Window title is derived from
        ``config.get("APP_NAME", "Talib Video Studio")`` if provided.
    """

    cleanup_finished = Signal()

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__()
        self._config = config or {}
        self._video_player: Optional["VideoPlayerWidget"] = None
        self._export_thread: Optional[ExportWorkerThread] = None
        self._setup_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the main window layout.

        Structure:
          - Top action bar: Import | Export (disabled) | file status label
          - Central viewport: VideoPlayerWidget
          - Bottom status bar: "Ready"
        """
        # Window basics
        app_name = self._config.get("APP_NAME", "Talib Video Studio")
        self.setWindowTitle(app_name)
        self.setMinimumSize(800, 600)

        # ------------------------------------------------------------------
        # Top action bar
        # ------------------------------------------------------------------
        action_bar = QWidget()
        action_bar.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
        import_btn = QPushButton("Import Video")
        import_btn.setObjectName("import_btn")
        import_btn.clicked.connect(self.handle_import)
        self.import_btn = import_btn  # store for enable/disable during export

        self.export_btn = QPushButton("Export Video")
        self.export_btn.setObjectName("export_btn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.handle_export)
        self.file_status = QLabel("No file loaded")
        self.file_status.setStyleSheet("margin-left: 12px;")

        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.addWidget(import_btn)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.export_btn)
        bar_layout.addWidget(self.file_status, 0)

        # ------------------------------------------------------------------
        # Central viewport — VideoPlayerWidget
        # ------------------------------------------------------------------
        from .player import VideoPlayerWidget

        self._video_player = VideoPlayerWidget()
        self._video_player.setSizePolicy(
            QFrame().sizePolicy()  # placeholder; real sizing in __init__
        )

        # ------------------------------------------------------------------
        # Main layout assembly
        # ------------------------------------------------------------------
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(action_bar)
        main_layout.addWidget(self._video_player, 1)  # stretch

        self.setCentralWidget(central)

        # Bottom status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        """Hook for subclasses / Parts 2–4 to connect additional signals."""
        pass

    # ------------------------------------------------------------------
    # Public API for Parts 2–4
    # ------------------------------------------------------------------

    def handle_import(self) -> None:
        """Open ImportMediaDialog and, on acceptance, load the chosen file.

        Enables the Export Video button and updates the status bar.
        """
        path = show_import_dialog(self)
        if path is None:
            return
        self.file_status.setText(f"File: {path.name}")
        self.export_btn.setEnabled(True)
        # Load the chosen media into the VideoPlayerWidget
        try:
            self._video_player.load_media(path)
        except Exception as exc:  # pragma: no cover
            self.status_bar.showMessage(f"Error loading media: {exc}")

    def handle_export(self) -> None:
        """Open ExportSettingsDialog, then run FFmpeg export in a background thread.

        Disables import/export buttons while exporting, updates the status bar,
        and shows a message box when the export finishes.
        """
        # Gather trim range from player
        trim_range = self._video_player.get_trim_range()
        # Input path – the player stores the loaded media path as a private attr
        input_path = getattr(self._video_player, "_media_path", Path(""))
        if not input_path or not input_path.is_file():
            self.status_bar.showMessage("No valid media loaded for export.")
            return

        settings = show_export_dialog(
            input_path,
            trim_range_ms=trim_range,
            parent=self,
        )
        if settings is None:
            return

        # Convert trim range (ms) to start/duration (seconds) if applicable
        start_sec: Optional[float] = None
        duration_sec: Optional[float] = None
        trim_in, trim_out = trim_range
        if trim_out > trim_in:
            start_sec = trim_in / 1000.0
            duration_sec = (trim_out - trim_in) / 1000.0

        # Prepare exporter and worker thread
        ffmpeg_path = self._config.get("FFMPEG_PATH", "ffmpeg")
        exporter = FFmpegExporter(ffmpeg_bin=ffmpeg_path)
        self._export_thread = ExportWorkerThread(
            exporter,
            input_path,
            settings["output_path"],
            resolution=settings["resolution"],
            fps=settings["fps"],
            start_sec=start_sec,
            duration_sec=duration_sec,
        )
        # Disable UI controls during export
        self.import_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status_bar.showMessage("Exporting…")
        self._export_thread.finished_export.connect(self._export_finished)
        self._export_thread.start()

    def _export_finished(self, success: bool, message: str) -> None:
        """Callback when ExportWorkerThread finishes.

        Re‑enables UI controls, updates the status bar, and shows a message box.
        """
        # Re‑enable buttons
        self.import_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        # Update status bar
        self.status_bar.showMessage(message, 5000)
        # Show a dialog
        from PySide6.QtWidgets import QMessageBox

        if success:
            QMessageBox.information(self, "Export Complete", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)
        # Clear reference to thread
        self._export_thread = None

    # ------------------------------------------------------------------
    # Video player integration hook
    # ------------------------------------------------------------------

    def set_video_player(self, widget: "VideoPlayerWidget") -> None:
        """Assign a VideoPlayerWidget into the central viewport.

        Parameters
        ----------
        widget: VideoPlayerWidget
            The player widget to display in the main window's viewport.
        """
        self._video_player = widget
        if self._video_player is not None:
            # Replace placeholder with actual player (if still present)
            old = self.centralWidget().layout().takeAt(
                self.centralWidget().layout().count() - 1
            )
            if old is not None:
                old.widget().setParent(None)
                old.widget().deleteLater()
            player_layout = self.centralWidget().layout()
            player_layout.addWidget(self._video_player, 1)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Stops any active export thread and notifies the main loop
        that cleanup is complete.
        """
        # Stop any active export thread
        if self._export_thread and self._export_thread.isRunning():
            self._export_thread.terminate()
            self._export_thread.wait()
        # Stop media playback
        if self._video_player:
            self._video_player._media_player.stop()
        # Notify cleanup complete
        self.cleanup_finished.emit()
        event.accept()