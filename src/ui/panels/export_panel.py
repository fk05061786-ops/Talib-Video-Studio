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
    QCheckBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QSlider,
    QPushButton,
    QFrame,
    QLineEdit,
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
)

from src.core.text_styles import (
    POSITIONS,
    TEXT_PRESETS,
    style_from_preset,
)
from src.core.render_presets import preset_choices, preset_to_export_settings
from src.core.grading import normalize_grade
from src.core.chroma import CHROMA_PRESETS, normalize_chroma
from src.core.proxy import normalize_proxy
from src.ui.panels.base_panel import BasePanel
from src.utils.ffmpeg import FFmpegExporter, ExportWorkerThread
from src.app.project import MediaClip


class ExportPanel(BasePanel):
    """Export Panel with effect controls and export configuration."""

    export_settings_changed = Signal(dict)
    export_started = Signal()
    export_progress = Signal(float)
    export_completed = Signal(bool, str)
    proxy_requested = Signal(str)

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

        # Render preset
        self._render_preset_labels = preset_choices()
        self._render_preset_combo = QComboBox()
        self._render_preset_combo.addItems(list(self._render_preset_labels))
        self._render_preset_combo.currentTextChanged.connect(
            self._apply_render_preset
        )
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Render preset:"))
        preset_row.addWidget(self._render_preset_combo, 1)
        settings_layout.addLayout(preset_row)

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

        # Text overlay
        self._text_edit = QLineEdit()
        self._text_edit.setPlaceholderText("Text overlay (optional)")
        settings_layout.addWidget(self._text_edit)

        preset_layout = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(TEXT_PRESETS))
        self._preset_combo.currentTextChanged.connect(self._apply_text_preset)
        preset_layout.addWidget(QLabel("Text preset:"))
        preset_layout.addWidget(self._preset_combo, 1)
        self._position_combo = QComboBox()
        self._position_combo.addItems(list(POSITIONS))
        preset_layout.addWidget(self._position_combo, 1)
        settings_layout.addLayout(preset_layout)

        duration_layout = QHBoxLayout()
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setRange(0.0, 3600.0)
        self._start_spin.setSuffix(" s")
        self._end_spin = QDoubleSpinBox()
        self._end_spin.setRange(0.0, 3600.0)
        self._end_spin.setSuffix(" s")
        duration_layout.addWidget(QLabel("From:"))
        duration_layout.addWidget(self._start_spin, 1)
        duration_layout.addWidget(QLabel("To:"))
        duration_layout.addWidget(self._end_spin, 1)
        settings_layout.addLayout(duration_layout)

        def slider_row(container, label, low, high, value):
            row = QHBoxLayout()
            control = QSlider(Qt.Horizontal)
            control.setRange(low, high)
            control.setValue(value)
            row.addWidget(QLabel(label))
            row.addWidget(control, 1)
            container.addLayout(row)
            return control

        # Color grading
        grade_frame = QFrame()
        grade_frame.setObjectName("panel-container")
        grade_layout = QVBoxLayout(grade_frame)
        grade_layout.addWidget(QLabel("Color Grading:"))
        self._brightness_slider = slider_row(grade_layout, "Brightness", -100, 100, 0)
        self._contrast_slider = slider_row(grade_layout, "Contrast", 0, 200, 100)
        self._saturation_slider = slider_row(grade_layout, "Saturation", 0, 200, 100)
        self._vibrance_slider = slider_row(grade_layout, "Vibrance", -100, 100, 0)
        self._warmth_slider = slider_row(grade_layout, "Warmth", -100, 100, 0)
        self._tint_slider = slider_row(grade_layout, "Tint", -100, 100, 0)
        settings_layout.addWidget(grade_frame)

        # Chroma key
        chroma_frame = QFrame()
        chroma_frame.setObjectName("panel-container")
        chroma_layout = QVBoxLayout(chroma_frame)
        self._chroma_enabled = QCheckBox("Enable Chroma Key")
        chroma_layout.addWidget(self._chroma_enabled)
        preset_row = QHBoxLayout()
        self._chroma_preset_combo = QComboBox()
        self._chroma_preset_combo.addItems(list(CHROMA_PRESETS))
        self._chroma_preset_combo.currentTextChanged.connect(
            self._apply_chroma_preset
        )
        self._chroma_color_combo = QComboBox()
        self._chroma_color_combo.addItems(["green", "blue", "white", "black"])
        preset_row.addWidget(QLabel("Preset:"))
        preset_row.addWidget(self._chroma_preset_combo, 1)
        preset_row.addWidget(self._chroma_color_combo, 1)
        chroma_layout.addLayout(preset_row)
        self._chroma_similarity_slider = slider_row(
            chroma_layout, "Similarity", 0, 100, 20
        )
        self._chroma_blend_slider = slider_row(chroma_layout, "Blend", 0, 100, 5)
        settings_layout.addWidget(chroma_frame)

        # Proxy editing
        proxy_frame = QFrame()
        proxy_frame.setObjectName("panel-container")
        proxy_layout = QVBoxLayout(proxy_frame)
        self._proxy_enabled = QCheckBox("Use Proxy Media")
        proxy_layout.addWidget(self._proxy_enabled)
        self._proxy_scale_slider = slider_row(proxy_layout, "Scale", 10, 100, 50)
        proxy_row = QHBoxLayout()
        self._proxy_resolution_combo = QComboBox()
        self._proxy_resolution_combo.addItems(["960x540", "1280x720", "640x360"])
        proxy_row.addWidget(QLabel("Proxy size:"))
        proxy_row.addWidget(self._proxy_resolution_combo, 1)
        proxy_layout.addLayout(proxy_row)
        self._generate_proxy_btn = QPushButton("Generate Proxy")
        self._generate_proxy_btn.clicked.connect(self._request_proxy)
        proxy_layout.addWidget(self._generate_proxy_btn)
        settings_layout.addWidget(proxy_frame)

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
        preset_key = settings.get("preset")
        for label, key in self._render_preset_labels.items():
            if key == preset_key:
                self._render_preset_combo.setCurrentText(label)
                break
        style = settings.get("text_style")
        if isinstance(style, dict):
            self._text_edit.setText(style.get("text", ""))
            if style.get("preset") in TEXT_PRESETS:
                self._preset_combo.setCurrentText(style["preset"])
            if style.get("position") in POSITIONS:
                self._position_combo.setCurrentText(style["position"])
            self._start_spin.setValue(float(style.get("start_sec") or 0))
            self._end_spin.setValue(float(style.get("end_sec") or 0))
        if "speed" in settings:
            self._speed_slider.setValue(int(float(settings["speed"]) * 5))
        if "volume" in settings:
            self._volume_slider.setValue(int(float(settings["volume"]) * 100))
        grade = normalize_grade(settings.get("grade"))
        for name, slider in (
            ("brightness", self._brightness_slider),
            ("contrast", self._contrast_slider),
            ("saturation", self._saturation_slider),
            ("vibrance", self._vibrance_slider),
            ("warmth", self._warmth_slider),
            ("tint", self._tint_slider),
        ):
            slider.setValue(int(round(getattr(grade, name) * 100)))
        chroma = normalize_chroma(settings.get("chroma"))
        self._chroma_enabled.setChecked(chroma.enabled)
        index = self._chroma_color_combo.findText(chroma.color)
        if index >= 0:
            self._chroma_color_combo.setCurrentIndex(index)
        self._chroma_similarity_slider.setValue(int(round(chroma.similarity * 100)))
        self._chroma_blend_slider.setValue(int(round(chroma.blend * 100)))
        proxy = normalize_proxy(settings.get("proxy"))
        self._proxy_enabled.setChecked(proxy.enabled)
        self._proxy_scale_slider.setValue(int(round(proxy.scale * 100)))
        if proxy.resolution in ("960x540", "1280x720", "640x360"):
            self._proxy_resolution_combo.setCurrentText(proxy.resolution)
        self._current_settings.update(settings)

    def current_settings(self) -> Dict[str, Any]:
        """Return all current export options for project serialization."""
        settings = dict(self._current_settings)
        settings["resolution"] = self._resolution_combo.currentText()
        settings["fps"] = self._fps_spin.value()
        settings["speed"] = self._speed_slider.value() / 5.0
        settings["volume"] = self._volume_slider.value() / 100.0
        settings["text_style"] = self._build_text_style()
        settings["grade"] = self.grade_settings()
        settings["chroma"] = self.chroma_settings()
        settings["proxy"] = self.proxy_settings()
        settings["preset"] = (
            self._render_preset_labels.get(self._render_preset_combo.currentText())
            or "custom"
        )
        return settings

    def _apply_render_preset(self, label: str) -> None:
        preset = preset_to_export_settings(self._render_preset_labels.get(label))
        if preset is None:
            return
        resolution = preset["resolution"]
        if self._resolution_combo.findText(resolution) < 0:
            self._resolution_combo.addItem(resolution)
        self._resolution_combo.setCurrentText(resolution)
        self._fps_spin.setValue(preset["fps"])

    def _apply_text_preset(self, name: str) -> None:
        position = TEXT_PRESETS.get(name, {}).get("position")
        if position in POSITIONS:
            self._position_combo.setCurrentText(position)

    def _build_text_style(self) -> Optional[Dict[str, Any]]:
        text = self._text_edit.text().strip()
        if not text:
            return None
        return style_from_preset(
            self._preset_combo.currentText(),
            text,
            position=self._position_combo.currentText(),
            start_sec=self._start_spin.value(),
            end_sec=self._end_spin.value(),
        ).to_dict()

    def grade_settings(self) -> Dict[str, Any]:
        """Return normalized color-grading values."""
        return normalize_grade(
            {
                "brightness": self._brightness_slider.value() / 100.0,
                "contrast": self._contrast_slider.value() / 100.0,
                "saturation": self._saturation_slider.value() / 100.0,
                "vibrance": self._vibrance_slider.value() / 100.0,
                "warmth": self._warmth_slider.value() / 100.0,
                "tint": self._tint_slider.value() / 100.0,
            }
        ).to_dict()

    def chroma_settings(self) -> Dict[str, Any]:
        """Return normalized chroma-key values."""
        return normalize_chroma(
            {
                "enabled": self._chroma_enabled.isChecked(),
                "color": self._chroma_color_combo.currentText(),
                "similarity": self._chroma_similarity_slider.value() / 100.0,
                "blend": self._chroma_blend_slider.value() / 100.0,
            }
        ).to_dict()

    def proxy_settings(self) -> Dict[str, Any]:
        """Return normalized proxy-editing values."""
        return normalize_proxy(
            {
                "enabled": self._proxy_enabled.isChecked(),
                "scale": self._proxy_scale_slider.value() / 100.0,
                "resolution": self._proxy_resolution_combo.currentText(),
                "folder": "proxies",
            }
        ).to_dict()

    def _apply_chroma_preset(self, name: str) -> None:
        preset = CHROMA_PRESETS.get(name)
        if preset is None:
            return
        color = str(preset.get("color", "green"))
        index = self._chroma_color_combo.findText(color)
        if index >= 0:
            self._chroma_color_combo.setCurrentIndex(index)
        self._chroma_similarity_slider.setValue(
            int(float(preset.get("similarity", 0.2)) * 100)
        )
        self._chroma_blend_slider.setValue(
            int(float(preset.get("blend", 0.05)) * 100)
        )

    def _request_proxy(self) -> None:
        source = self._current_settings.get("input_path")
        if not source:
            QMessageBox.warning(self, "Proxy Error", "No media file loaded.")
            return
        self.proxy_requested.emit(str(source))

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
            speed=speed,
            volume=volume,
            text_style=self._build_text_style(),
            grade=self.grade_settings(),
            chroma=self.chroma_settings(),
        )
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
