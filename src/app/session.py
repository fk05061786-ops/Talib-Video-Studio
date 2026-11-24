"""Session management for Talib Video Studio.

Handles application session state, UI persistence, and recent projects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class WindowState:
    """Represents window state for persistence."""

    x: int
    y: int
    width: int
    height: int
    maximized: bool = False
    fullscreen: bool = False


@dataclass
class PanelState:
    """Represents panel state for persistence."""

    visible: bool = True
    width: int = 200
    height: int = 300
    x: int = 0
    y: int = 0


class Session:
    """Manages application session state."""

    def __init__(self) -> None:
        self.project_path: Optional[Path] = None
        self.window_state: WindowState = WindowState(100, 100, 1200, 800)
        self.panel_states: Dict[str, PanelState] = {}
        self.recent_projects: List[Path] = []
        self.ui_preferences: Dict[str, Any] = {
            "theme": "dark",
            "language": "en",
            "auto_save": True,
            "auto_save_interval": 300,  # seconds
        }
        self.last_opened: Optional[datetime] = None

    def add_recent_project(self, path: Path) -> None:
        """Add a project to recent projects list."""
        if path not in self.recent_projects:
            self.recent_projects.insert(0, path)
            # Keep only last 10 projects
            self.recent_projects = self.recent_projects[:10]

    def get_panel_state(self, panel_id: str) -> PanelState:
        """Get panel state, create default if not exists."""
        if panel_id not in self.panel_states:
            self.panel_states[panel_id] = PanelState()
        return self.panel_states[panel_id]

    def set_panel_state(self, panel_id: str, state: PanelState) -> None:
        """Set panel state."""
        self.panel_states[panel_id] = state

    def save_session(self, path: Path) -> bool:
        """Save session state to JSON file."""
        try:
            session_data = {
                "window_state": asdict(self.window_state),
                "panel_states": {pid: asdict(state) for pid, state in self.panel_states.items()},
                "recent_projects": [str(p) for p in self.recent_projects],
                "ui_preferences": self.ui_preferences,
                "last_opened": self.last_opened.isoformat() if self.last_opened else None,
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)

            return True
        except Exception:
            return False

    def load_session(self, path: Path) -> bool:
        """Load session state from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            self.window_state = WindowState(**session_data["window_state"])
            self.panel_states = {
                pid: PanelState(**state) for pid, state in session_data["panel_states"].items()
            }
            self.recent_projects = [Path(p) for p in session_data["recent_projects"]]
            self.ui_preferences = session_data.get("ui_preferences", {})
            self.last_opened = (
                datetime.fromisoformat(session_data["last_opened"])
                if session_data.get("last_opened")
                else None
            )

            return True
        except Exception:
            return False