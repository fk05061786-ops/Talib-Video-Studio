"""MainWindow for Talib Video Studio.

Provides the central application window with a dark-themed UI, action bar,
video player viewport, and status bar. Designed so Parts 2–4 can plug in
via clear method hooks without rewriting the window structure.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from typing import Any
from PySide6.QtCore import Qt, Signal, QObject, QEvent, QKeySequence
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
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
    QFileDialog,
    QMessageBox,
)

from .dialogs import show_import_dialog, show_export_dialog
from .panels import ExportPanel, MonitorPanel, TimelinePanel
from src.core.media import get_media_info
from src.core.export_validation import validate_export_request
from src.core.undo import TimelineState
from src.core.project_file import (
    PROJECT_EXTENSION,
    ProjectDocument,
    load_project,
    save_project as write_project,
)
from src.core.proxy import ProxyManager, normalize_proxy
from src.core.shortcuts import (
    ShortcutAction,
    dispatch_shortcut,
    is_text_input_class,
    resolve_shortcut,
)
from src.app.project import Project
from src.app.startup import init_effect_registry
from src.utils.ffmpeg import FFmpegExporter, ExportWorkerThread
from src.utils.packaging import resolve_binary
from src.app.session import Session

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for Talib Video Studio.

    Parameters
    ----------
    config: dict | None, optional
        Configuration dictionary. Window title is derived from
        ``config.get("APP_NAME", "Talib Video Studio")`` if provided.
    """

    cleanup_finished = Signal()

    def __init__(
        self,
        config: Optional[dict] = None,
        registry: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self._config = config or {}
        self.effect_registry = (
            registry if registry is not None else init_effect_registry(self._config)
        )
        self._video_player: Optional["VideoPlayerWidget"] = None
        self._monitor_panel: Optional[MonitorPanel] = None
        self._timeline_panel: Optional[TimelinePanel] = None
        self._export_panel: Optional[ExportPanel] = None
        self._import_seq = 0
        self._main_splitter: Optional[QSplitter] = None
        self._export_thread: Optional[ExportWorkerThread] = None
        self._project = Project()
        self._session = Session()
        self._proxy_manager = ProxyManager()
        self._setup_ui()
        self._wire_signals()
        self._install_shortcuts()

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

        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.open_project)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_project)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self.redo)

        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.triggered.connect(self.undo)
        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut("Ctrl+Y")
        self._redo_action.triggered.connect(self.redo)
        self._redo_alt_action = QAction("Redo", self)
        self._redo_alt_action.setShortcut("Ctrl+Shift+Z")
        self._redo_alt_action.triggered.connect(self.redo)
        self._open_action = QAction("Open Project", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.triggered.connect(self.open_project)
        self._save_action = QAction("Save Project", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self.save_project)
        self._save_as_action = QAction("Save Project As...", self)
        self._save_as_action.setShortcut("Ctrl+Shift+S")
        self._save_as_action.triggered.connect(self.save_as_project)
        self._generate_proxy_action = QAction("Generate Proxy", self)
        self._generate_proxy_action.setShortcut("Ctrl+P")
        self._generate_proxy_action.triggered.connect(self.generate_proxy)
        self._use_proxies_action = QAction("Use Proxy Media", self)
        self._use_proxies_action.setCheckable(True)
        self._use_proxies_action.toggled.connect(self.toggle_proxies)
        for action in (
            self._undo_action,
            self._redo_action,
            self._redo_alt_action,
            self._open_action,
            self._save_action,
            self._save_as_action,
            self._generate_proxy_action,
            self._use_proxies_action,
        ):
            self.addAction(action)

        self.export_btn = QPushButton("Export Video")
        self.export_btn.setObjectName("export_btn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.handle_export)
        self.file_status = QLabel("No file loaded")
        self.file_status.setStyleSheet("margin-left: 12px;")

        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.addWidget(import_btn)
        bar_layout.addWidget(self.open_btn)
        bar_layout.addWidget(self.save_btn)
        bar_layout.addWidget(self.undo_btn)
        bar_layout.addWidget(self.redo_btn)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.export_btn)
        bar_layout.addWidget(self.file_status, 0)

        # ------------------------------------------------------------------
        # Central viewport — player above the timeline
        # ------------------------------------------------------------------
        from .player import VideoPlayerWidget

        self._video_player = VideoPlayerWidget()

        self._timeline_panel = TimelinePanel(self)
        self._main_splitter = QSplitter(Qt.Vertical)
        self._main_splitter.addWidget(self._video_player)
        self._main_splitter.addWidget(self._timeline_panel)
        self._main_splitter.setSizes([400, 200])

        # Monitor lives in a side dock so both views stay visible.
        self._monitor_panel = MonitorPanel(self)
        monitor_dock = QDockWidget("Monitor", self)
        monitor_dock.setObjectName("monitor_dock")
        monitor_dock.setWidget(self._monitor_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, monitor_dock)

        self._export_panel = ExportPanel(self)
        export_dock = QDockWidget("Export Effects", self)
        export_dock.setObjectName("export_dock")
        export_dock.setWidget(self._export_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, export_dock)
        self.tabifyDockWidget(monitor_dock, export_dock)

        # ------------------------------------------------------------------
        # Main layout assembly
        # ------------------------------------------------------------------
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(action_bar)
        main_layout.addWidget(self._main_splitter, 1)  # stretch

        self.setCentralWidget(central)

        # Bottom status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        """Connect monitor playback/scrub to the timeline playhead (two-way)."""
        if self._monitor_panel is None or self._timeline_panel is None:
            return
        self._monitor_panel.playhead_position.connect(
            self._timeline_panel.set_playhead
        )
        self._timeline_panel.playhead_moved.connect(
            self._monitor_panel.set_position
        )
        self._monitor_panel.in_point_set.connect(
            lambda ms: self.status_bar.showMessage(f"In point: {ms} ms", 3000)
        )
        self._monitor_panel.out_point_set.connect(
            lambda ms: self.status_bar.showMessage(f"Out point: {ms} ms", 3000)
        )
        self._timeline_panel.clip_razored.connect(
            lambda _old_id, parts: self.status_bar.showMessage(
                f"Split clip into {len(parts)} parts", 3000
            )
        )
        self._timeline_panel.transition_added.connect(
            lambda data: self.status_bar.showMessage(
                f"{data['kind']} added ({data['duration_ms']} ms)", 3000
            )
        )
        self._timeline_panel.undo_state_changed.connect(
            self._on_history_changed
        )
        if self._export_panel is not None:
            self._export_panel.proxy_requested.connect(self.generate_proxy)

    # ------------------------------------------------------------------
    # Proxy editing
    # ------------------------------------------------------------------

    def toggle_proxies(self, enabled: bool) -> None:
        """Enable/disable proxy playback using the export-panel settings."""
        settings = (
            self._export_panel.proxy_settings()
            if self._export_panel is not None
            else {}
        )
        settings["enabled"] = bool(enabled)
        self._proxy_manager.set_settings(settings)
        if self._export_panel is not None:
            current = self._export_panel.current_settings()
            current["proxy"] = self._proxy_manager.settings.to_dict()
            self._export_panel.set_export_settings(current)
        self.status_bar.showMessage(
            "Proxy media enabled" if enabled else "Proxy media disabled", 3000
        )

    def generate_proxy(self, source: Optional[str] = None) -> bool:
        """Generate a proxy for the current source media with error handling."""
        if not source:
            source = getattr(self._video_player, "_media_path", None)
        if not source:
            QMessageBox.warning(self, "Proxy Error", "No media file loaded.")
            return False
        try:
            self._proxy_manager.set_settings(
                self._export_panel.proxy_settings()
                if self._export_panel is not None
                else None
            )
            ok, message = self._proxy_manager.ensure(source)
        except Exception:
            logger.exception("Proxy generation failed")
            QMessageBox.critical(self, "Proxy Error", "Unexpected proxy error.")
            return False
        if not ok:
            logger.error("Proxy generation failed: %s", message)
            QMessageBox.critical(self, "Proxy Error", message)
            self.status_bar.showMessage(message, 5000)
            return False
        self.status_bar.showMessage(f"Proxy ready: {message}", 5000)
        return True

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _on_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        """Keep buttons, shortcuts and status in sync with the history stack."""
        self.undo_btn.setEnabled(bool(can_undo))
        self.redo_btn.setEnabled(bool(can_redo))
        self._undo_action.setEnabled(bool(can_undo))
        self._redo_action.setEnabled(bool(can_redo))
        self._redo_alt_action.setEnabled(bool(can_redo))

    def undo(self) -> None:
        """Undo the latest timeline edit with guarded error handling."""
        if self._timeline_panel is None:
            return
        try:
            if self._timeline_panel.undo():
                self.status_bar.showMessage("Undo", 2000)
        except Exception:
            logger.exception("Undo failed")
            self.status_bar.showMessage("Undo failed (see log)", 5000)

    def redo(self) -> None:
        """Redo the latest undone timeline edit with guarded error handling."""
        if self._timeline_panel is None:
            return
        try:
            if self._timeline_panel.redo():
                self.status_bar.showMessage("Redo", 2000)
        except Exception:
            logger.exception("Redo failed")
            self.status_bar.showMessage("Redo failed (see log)", 5000)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _install_shortcuts(self) -> None:
        """Register NLE key handlers and an application-wide event filter."""
        self._shortcut_handlers = {
            "play_pause": self._shortcut_play_pause,
            "previous_frame": self._shortcut_previous_frame,
            "next_frame": self._shortcut_next_frame,
            "set_in": self._shortcut_set_in,
            "set_out": self._shortcut_set_out,
            "clear_trim": self._shortcut_clear_trim,
            "split": self._shortcut_split,
            "delete": self._shortcut_delete,
            "ripple_delete": self._shortcut_ripple_delete,
            "select_tool": self._shortcut_select_tool,
            "razor_tool": self._shortcut_razor_tool,
        }
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Dispatch NLE shortcuts, ignoring keys typed into text widgets."""
        if event.type() == QEvent.KeyPress and self.isActiveWindow():
            class_name = (
                obj.metaObject().className()
                if hasattr(obj, "metaObject")
                else type(obj).__name__
            )
            if not is_text_input_class(class_name):
                sequence = QKeySequence(
                    int(event.modifiers()) | event.key()
                ).toString()
                action = resolve_shortcut(sequence, context="nle")
                if action is not None:
                    self._dispatch_binding(action)
                    return True
        return super().eventFilter(obj, event)

    def _dispatch_binding(self, action: ShortcutAction) -> None:
        """Run a resolved shortcut with guarded error handling."""
        try:
            dispatch_shortcut(action, self._shortcut_handlers)
        except Exception:
            logger.exception("Shortcut %s failed", action.action_id)
            self.status_bar.showMessage("Shortcut failed (see log)", 5000)

    def _shortcut_play_pause(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.play_pause()

    def _shortcut_previous_frame(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.previous_frame()

    def _shortcut_next_frame(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.next_frame()

    def _shortcut_set_in(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.set_in()

    def _shortcut_set_out(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.set_out()

    def _shortcut_clear_trim(self) -> None:
        if self._monitor_panel is not None:
            self._monitor_panel.clear_trim()

    def _shortcut_split(self) -> None:
        if self._timeline_panel is not None and not self._timeline_panel.split_at_playhead():
            self.status_bar.showMessage("No editable clip at playhead", 3000)

    def _shortcut_delete(self) -> None:
        if self._timeline_panel is not None and not self._timeline_panel.delete_selected():
            self.status_bar.showMessage("No editable clip selected", 3000)

    def _shortcut_ripple_delete(self) -> None:
        if self._timeline_panel is not None and not self._timeline_panel.delete_selected(ripple=True):
            self.status_bar.showMessage("No editable clip selected", 3000)

    def _shortcut_select_tool(self) -> None:
        if self._timeline_panel is not None:
            self._timeline_panel.set_tool("select")

    def _shortcut_razor_tool(self) -> None:
        if self._timeline_panel is not None:
            self._timeline_panel.set_tool("razor")

    # ------------------------------------------------------------------
    # Project save / load
    # ------------------------------------------------------------------

    def current_project_path(self) -> Optional[Path]:
        """Return the path of the currently open project, if any."""
        return self._session.project_path

    def _build_document(self) -> ProjectDocument:
        settings = (
            self._export_panel.current_settings() if self._export_panel else {}
        )
        return ProjectDocument(
            name=self._project.name,
            timeline=(
                self._timeline_panel.snapshot()
                if self._timeline_panel
                else TimelineState()
            ),
            playhead_ms=(
                self._timeline_panel.get_playhead() if self._timeline_panel else 0
            ),
            export_settings=settings,
            text_style=settings.get("text_style"),
            created_at=self._project.created_at.isoformat(),
            modified_at=datetime.now().isoformat(),
        )

    def save_project(self) -> bool:
        """Save to the current project path, or prompt with Save As."""
        path = self._session.project_path
        if path is None:
            return self.save_as_project()
        return self._write_project(path)

    def save_as_project(self) -> bool:
        """Prompt for a ``.tvs`` path and save the project there."""
        default = Path.cwd() / f"{self._project.name.replace(' ', '_')}{PROJECT_EXTENSION}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(self._session.project_path or default),
            f"Talib Video Studio Project (*{PROJECT_EXTENSION})",
        )
        if not path:
            return False
        return self._write_project(Path(path), update_path=True)

    def _write_project(self, path: Path, update_path: bool = False) -> bool:
        try:
            success, message = write_project(path, self._build_document())
        except Exception:
            logger.exception("Save project failed")
            QMessageBox.critical(self, "Save Failed", "Unexpected error while saving.")
            return False
        if not success:
            logger.error("Save project failed: %s", message)
            QMessageBox.critical(self, "Save Failed", message)
            self.status_bar.showMessage(message, 5000)
            return False

        target = Path(message)
        self._project.modified_at = datetime.now()
        if update_path or self._session.project_path is None:
            self._session.project_path = target
        self._session.add_recent_project(target)
        self._session.last_opened = datetime.now()
        self.setWindowTitle(f"{self._project.name} — Talib Video Studio")
        self.status_bar.showMessage(f"Saved {target.name}", 3000)
        return True

    def open_project(self) -> bool:
        """Prompt for a ``.tvs`` project and restore its full state."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(self._session.project_path or Path.cwd()),
            f"Talib Video Studio Project (*{PROJECT_EXTENSION})",
        )
        if not path:
            return False
        try:
            document, message = load_project(Path(path))
        except Exception:
            logger.exception("Open project failed")
            QMessageBox.critical(self, "Open Failed", "Unexpected error while opening.")
            return False
        if document is None:
            logger.error("Open project failed: %s", message)
            QMessageBox.critical(self, "Open Failed", message)
            self.status_bar.showMessage(message, 5000)
            return False
        try:
            self._restore_document(document, Path(path))
        except Exception:
            logger.exception("Restoring project failed")
            QMessageBox.critical(self, "Open Failed", "Could not restore project state.")
            return False

        self.status_bar.showMessage(message, 5000)
        if "missing" in message:
            QMessageBox.warning(self, "Missing Source Media", message)
        return True

    def _restore_document(self, document: ProjectDocument, path: Path) -> None:
        self._project.name = document.name
        self._project.created_at = (
            datetime.fromisoformat(document.created_at)
            if document.created_at
            else datetime.now()
        )
        self._project.modified_at = (
            datetime.fromisoformat(document.modified_at)
            if document.modified_at
            else datetime.now()
        )
        if self._timeline_panel is not None:
            self._timeline_panel.apply_state(
                document.timeline, document.playhead_ms, reset_history=True
            )
        if self._export_panel is not None:
            settings = dict(document.export_settings)
            if document.text_style is not None:
                settings["text_style"] = document.text_style
            self._export_panel.set_export_settings(settings)
        proxy_data = document.export_settings.get("proxy")
        if proxy_data is not None:
            self._proxy_manager.set_settings(proxy_data)
            self._use_proxies_action.setChecked(
                normalize_proxy(proxy_data).enabled
            )

        self._session.project_path = path
        self._session.add_recent_project(path)
        self._session.last_opened = datetime.now()
        self.setWindowTitle(f"{document.name} — Talib Video Studio")

        first_path = next(
            (str(clip.get("path")) for clip in document.timeline.clips if clip.get("path")),
            None,
        )
        if first_path and Path(first_path).is_file():
            self._video_player.load_media(Path(first_path))
            if self._monitor_panel is not None:
                self._monitor_panel.set_source_media(first_path)
            self.file_status.setText(f"File: {Path(first_path).name}")
            self.export_btn.setEnabled(True)
        else:
            self.file_status.setText("No media loaded")
            self.export_btn.setEnabled(False)

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
        # Load the chosen media into the player and the source monitor
        try:
            self._video_player.load_media(path)
            if self._monitor_panel is not None:
                self._monitor_panel.set_source_media(str(path))
            info = get_media_info(str(path))
            duration_ms = int(info.get("duration", 0) * 1000)
            self._import_seq += 1
            base = {
                "name": path.name,
                "path": str(path),
                "duration": duration_ms,
                "format": info.get("format", ""),
            }
            if self._timeline_panel is not None and duration_ms > 0:
                self._timeline_panel.add_clip_to_timeline(
                    {**base, "id": f"v{self._import_seq}"}, 1, 0
                )
                self._timeline_panel.add_clip_to_timeline(
                    {**base, "id": f"a{self._import_seq}"}, 2, 0
                )
            if self._export_panel is not None:
                self._export_panel.set_export_settings(
                    {
                        "input_path": path,
                        "resolution": "1920x1080",
                        "fps": 30,
                    }
                )
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

        # Resolve binaries and validate before starting a background job
        from PySide6.QtWidgets import QMessageBox

        proxy_settings = settings.get("proxy")
        if proxy_settings is not None:
            self._proxy_manager.set_settings(proxy_settings)
        export_source = self._proxy_manager.resolve(input_path)
        if export_source != input_path:
            self.status_bar.showMessage("Exporting from proxy media", 3000)

        ffmpeg_path = (
            resolve_binary("ffmpeg", self._config)
            or self._config.get("FFMPEG_PATH", "ffmpeg")
        )
        error = validate_export_request(
            export_source, settings["output_path"], ffmpeg_path
        )
        if error:
            QMessageBox.warning(self, "Export Error", error)
            self.status_bar.showMessage(error)
            return

        exporter = FFmpegExporter(ffmpeg_bin=ffmpeg_path)
        self._export_thread = ExportWorkerThread(
            exporter,
            export_source,
            settings["output_path"],
            resolution=settings["resolution"],
            fps=settings["fps"],
            start_sec=start_sec,
            duration_sec=duration_sec,
            grade=settings.get("grade"),
            chroma=settings.get("chroma"),
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
        if self._video_player is None or self._main_splitter is None:
            return
        old = self._main_splitter.widget(0)
        if old is not None:
            old.setParent(None)
            old.deleteLater()
        self._main_splitter.insertWidget(0, self._video_player, 1)

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
        if self._monitor_panel:
            self._monitor_panel.stop_all()
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        # Notify cleanup complete
        self.cleanup_finished.emit()
        event.accept()