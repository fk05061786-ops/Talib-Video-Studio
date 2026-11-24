"""Media Bin panel for Talib Video Studio.

Displays imported clips with metadata and provides selection/drag
functionality. Uses Premiere Pro-inspired dark theme.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QFrame,
)

from src.ui.panels.base_panel import BasePanel
from src.app.project import MediaClip
from src.core.media import get_clip_thumbnail


class MediaBinPanel(BasePanel):
    """Media Bin panel displaying imported clips.

    Emits ``clip_selected`` when a clip is selected and ``clip_dropped``
    when a clip is dragged onto the timeline.
    """

    clip_selected = Signal(dict)
    clip_dropped = Signal(dict, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._clips: List[MediaClip] = []
        self._selected_clip: Optional[MediaClip] = None
        self._thumbnail_cache: Dict[str, Path] = {}

    def setup_ui(self) -> None:
        """Build the media bin UI with dark theme styling.
        """
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Header - styled
        header = QLabel("Media Bin")
        header.setObjectName("panel-title")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: var(--panel-header-fg);")
        main_layout.addWidget(header)

        # Clip list
        self._clip_list = QListWidget()
        self._clip_list.setSelectionMode(QListWidget.SingleSelection)
        self._clip_list.itemClicked.connect(self._on_clip_clicked)
        self._clip_list.setMinimumHeight(200)
        self._clip_list.setStyleSheet("background-color: var(--bg-light); border: 1px solid var(--border-mid);")
        main_layout.addWidget(self._clip_list)

        # Details panel
        self._details_frame = QFrame()
        self._details_frame.setObjectName("panel-container")
        self._details_frame.setStyleSheet(
            "background-color: var(--bg-light); border: 1px solid var(--border-dark);"
        )
        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setContentsMargins(8, 8, 8, 8)

        self._detail_name = QLabel("Select a clip to view details")
        self._detail_name.setWordWrap(True)
        self._detail_info = QLabel()
        self._detail_thumbnail = QLabel()
        self._detail_thumbnail.setFixedSize(160, 90)
        self._detail_thumbnail.setScaledContents(True)
        self._detail_thumbnail.setStyleSheet("background-color: var(--bg-dark); border: 1px solid var(--border-dark);")

        details_layout.addWidget(QLabel("Details:", styleSheet="font-weight: bold; color: var(--text-primary);"))
        details_layout.addWidget(self._detail_name)
        details_layout.addWidget(self._detail_info)
        details_layout.addWidget(self._detail_thumbnail)

        main_layout.addWidget(self._details_frame)

    def connect_signals(self) -> None:
        """Wire up internal signals.
        """
        # Connect to project updates when available
        pass

    def set_clips(self, clips: List[MediaClip]) -> None:
        """Set the clips to display in the bin.
        """
        self._clips = clips
        self._clip_list.clear()
        for clip in clips:
            item = QListWidgetItem(f"{clip.name} ({clip.format})")
            item.setData(Qt.UserRole, clip.id)
            self._clip_list.addItem(item)
        self._update_details()

    def get_selected_clip(self) -> Optional[MediaClip]:
        """Return the currently selected clip.
        """
        item = self._clip_list.currentItem()
        if item:
            clip_id = item.data(Qt.UserRole)
            for clip in self._clips:
                if clip.id == clip_id:
                    return clip
        return None

    def _on_clip_clicked(self, item: QListWidgetItem) -> None:
        """Handle clip selection.
        """
        clip_id = item.data(Qt.UserRole)
        for clip in self._clips:
            if clip.id == clip_id:
                self._selected_clip = clip
                self.clip_selected.emit(clip.to_dict())
                self._update_details()
                break

    def _update_details(self) -> None:
        """Update the details panel based on selected clip.
        """
        clip = self._selected_clip
        if not clip:
            self._detail_name.setText("Select a clip to view details")
            self._detail_info.setText("")
            self._detail_thumbnail.setStyleSheet("background-color: var(--bg-dark); border: 1px solid var(--border-dark);")
            return

        self._detail_name.setText(f"{clip.name}")
        self._detail_info.setText(
            f"Duration: {clip.duration:.2f}s\n"
            f"Resolution: {clip.resolution}\n"
            f"Format: {clip.format}\n"
            f"Size: {clip.size / (1024*1024):.2f} MB"
        )

        # Load thumbnail if available
        thumbnail_path = self._get_thumbnail_path(clip)
        if thumbnail_path and thumbnail_path.exists():
            self._detail_thumbnail.setPixmap(
                get_clip_thumbnail(str(thumbnail_path), self._detail_thumbnail.width(), self._detail_thumbnail.height())
            )
        else:
            self._detail_thumbnail.setStyleSheet("background-color: var(--bg-dark); border: 1px solid var(--border-dark);")

    def _get_thumbnail_path(self, clip: MediaClip) -> Optional[Path]:
        """Return cached thumbnail path or generate if needed.
        """
        if clip.id in self._thumbnail_cache:
            return self._thumbnail_cache[clip.id]

        # Generate thumbnail path
        thumbnail_dir = Path("assets/thumbnails")
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = thumbnail_dir / f"{clip.id}.jpg"
        self._thumbnail_cache[clip.id] = thumbnail_path
        return thumbnail_path