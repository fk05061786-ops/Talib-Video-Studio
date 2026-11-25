"""Dialogs for Talib Video Studio.

Provides media import and export configuration dialogs used by MainWindow.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QFrame,
)
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from src.core.render_presets import preset_choices, preset_to_export_settings


SUPPORTED_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm"})


def _is_supported_path(path: Path) -> bool:
    """Return True if *path* has a supported video extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


# ------------------------------------------------------------------
# ImportMediaDialog
# ------------------------------------------------------------------


class ImportMediaDialog(QDialog):
    """Dialog for importing a media file.

    Lets the user browse for or type/paste a video file path.  Validates
    that the selected path exists, is a file, and has a supported
    extension before accepting.

    Returns
    -------
    selected_file: Path | None
        The Path the user chose, or ``None`` if cancelled.
    """

    def __init__(self, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Media")
        self.resize(400, 120)

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------
        layout = QVBoxLayout(self)

        # Path display + browse
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select or paste a video file path...")
        self._path_edit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r".*"), self._path_edit
            )
        )
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)

        path_layout.addWidget(self._path_edit, 1)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Open")
        self.btn_ok.clicked.connect(self._accept_if_valid)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def selected_file(self) -> Optional[Path]:
        """Return the path the user chose, or ``None`` if cancelled."""
        path_text = self._path_edit.text().strip()
        if not path_text:
            return None
        p = Path(path_text).resolve()
        if p.exists() and p.is_file() and _is_supported_path(p):
            return p
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        """Open a file dialog and fill the path edit."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if path:
            self._path_edit.setText(path)

    def _accept_if_valid(self) -> None:
        """Validate the path and accept or show a warning."""
        p = self.selected_file()
        if p is None:
            QMessageBox.warning(
                self,
                "Invalid path",
                "Please select a valid video file with a supported extension "
                "(mp4, mov, mkv, avi, webm).",
            )
        else:
            self.accept()


# ------------------------------------------------------------------
# ExportSettingsDialog
# ------------------------------------------------------------------


class ExportSettingsDialog(QDialog):
    """Dialog for configuring export settings.

    Parameters
    ----------
    input_path: Path
        The source media file to export.
    trim_range_ms: tuple[int, int] | None, optional
        (trim_in_ms, trim_out_ms) if a trim has been set, otherwise ``None``.
    parent: QWidget | None, optional
        Parent widget.
    """

    def __init__(
        self,
        input_path: Path,
        trim_range_ms: Optional[tuple[int, int]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Video")
        self.resize(420, 280)

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------
        layout = QVBoxLayout(self)

        # Input path read-only display
        self._input_path = input_path
        self._trim_range_ms = trim_range_ms
        path_label = QLabel(f"Input: {input_path.name}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Output path
        out_layout = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Output path (optional)")
        # Default: <stem>_exported.mp4 in same directory
        default_out = input_path.parent / f"{input_path.stem}_exported.mp4"
        self._output_edit.setText(str(default_out))
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(self._output_edit, 1)
        out_layout.addWidget(out_btn)
        layout.addLayout(out_layout)

        # Render preset
        self._preset_labels = preset_choices()
        self._render_preset_combo = QComboBox()
        self._render_preset_combo.addItems(list(self._preset_labels))
        self._render_preset_combo.currentTextChanged.connect(
            self._apply_render_preset
        )
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Render preset:"))
        preset_row.addWidget(self._render_preset_combo, 1)
        layout.addLayout(preset_row)

        # Resolution
        res_layout = QHBoxLayout()
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(
            ["1920x1080", "1280x720", "1080x1920"]
        )
        # Select the one matching the input if sensible
        res_layout.addWidget(QLabel("Resolution:"))
        res_layout.addWidget(self._resolution_combo, 1)
        layout.addLayout(res_layout)

        # FPS
        fps_layout = QHBoxLayout()
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(15, 60)
        self._fps_spin.setValue(30)
        fps_layout.addWidget(QLabel("FPS:"))
        fps_layout.addWidget(self._fps_spin, 1)
        layout.addLayout(fps_layout)

        # Trim range summary
        if trim_range_ms:
            tin, tout = trim_range_ms
            trim_text = f"Trim: {tin}ms – {tout}ms"
        else:
            trim_text = "No trim"
        self._trim_label = QLabel(trim_text)
        self._trim_label.setWordWrap(True)
        layout.addWidget(self._trim_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Export")
        self.btn_ok.clicked.connect(self._accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def export_settings(self) -> dict:
        """Return the configured export settings dict.

        Returns
        -------
        dict
            ``{"output_path": Path, "resolution": str, "fps": int,
            "trim_range_ms": tuple[int, int] | None}``.
        """
        out_path = Path(self._output_edit.text().strip() or str(
            self._input_path.parent / f"{self._input_path.stem}_exported.mp4"
        ))
        # Ensure .mp4 extension
        if out_path.suffix.lower() != ".mp4":
            out_path = out_path.with_suffix(".mp4")
        settings = {
            "output_path": out_path,
            "resolution": self._resolution_combo.currentText(),
            "fps": self._fps_spin.value(),
            "trim_range_ms": self._trim_range_ms,
        }
        preset = preset_to_export_settings(
            self._preset_labels.get(self._render_preset_combo.currentText())
        )
        settings["preset"] = preset["preset"] if preset else "custom"
        if preset:
            for key in ("video_bitrate", "audio_bitrate", "codec", "audio_codec"):
                settings[key] = preset[key]
        return settings

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_render_preset(self, label: str) -> None:
        settings = preset_to_export_settings(self._preset_labels.get(label))
        if settings is None:
            return
        resolution = settings["resolution"]
        if self._resolution_combo.findText(resolution) < 0:
            self._resolution_combo.addItem(resolution)
        self._resolution_combo.setCurrentText(resolution)
        self._fps_spin.setValue(settings["fps"])

    def _browse_output(self) -> None:
        """Open a save dialog for the output path."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video As",
            self._output_edit.text(),
            "MP4 Files (*.mp4);;All Files (*)",
        )
        if path:
            self._output_edit.setText(path)

    def _accept(self) -> None:
        """Validate and accept the dialog."""
        # Basic validation: output path must be writable location
        out = self._output_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "Missing output", "Please specify an output path.")
            return
        self.accept()


# ------------------------------------------------------------------
# Convenience shim so MainWindow can call dialogs inline
# ------------------------------------------------------------------


def show_import_dialog(parent=None) -> Optional[Path]:
    """Show ``ImportMediaDialog`` and return the chosen path or ``None``."""
    d = ImportMediaDialog(parent)
    if d.exec():
        return d.selected_file()
    return None


def show_export_dialog(
    input_path: Path,
    trim_range_ms: Optional[tuple[int, int]] = None,
    parent=None,
) -> Optional[dict]:
    """Show ``ExportSettingsDialog`` and return the settings dict or ``None``."""
    d = ExportSettingsDialog(input_path, trim_range_ms, parent)
    if d.exec():
        return d.export_settings()
    return None