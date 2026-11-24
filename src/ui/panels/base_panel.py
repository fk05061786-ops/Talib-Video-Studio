"""Base panel class for Talib Video Studio UI panels.

Provides the foundation for all UI panels with common functionality,
signals, and integration points with the main window.
"""

from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Slot


class BasePanel(QWidget):
    """Base class for all UI panels in the application.

    Subclasses should implement ``setup_ui`` and ``connect_signals`` methods.
    ``setup_ui`` builds the panel's UI, ``connect_signals`` wires up
    internal signals to slots.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        """Build the panel's UI.

        Subclasses must implement this method to create their widgets
        and layout.
        """
        raise NotImplementedError("Subclasses must implement setup_ui")

    def connect_signals(self) -> None:
        """Wire up internal signals to slots.

        Subclasses should implement this method to connect their own
        signals to appropriate slots.
        """
        raise NotImplementedError("Subclasses must implement connect_signals")

    # ------------------------------------------------------------------
    # Common panel functionality
    # ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or hide the panel."""
        self.setVisible(visible)

    def is_visible(self) -> bool:
        """Return whether the panel is currently visible."""
        return self.isVisible()

    def set_parent(self, parent: QWidget) -> None:
        """Set the panel's parent widget."""
        self.setParent(parent)

    def update_content(self) -> None:
        """Refresh panel content.

        Subclasses can override this to update their UI based on model
        changes.
        """
        pass