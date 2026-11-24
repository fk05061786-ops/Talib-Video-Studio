"""Tal Video Studio — main entry point.

Loads environment variables from ``.env.hub`` (project root) and displays
the :class:`MainWindow` with the loaded configuration.  Handles cleanup
on shutdown and top-level errors gracefully.
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

# ------------------------------------------------------------------
# Load .env.hub  (key=value, ignore blanks and # comments, strip quotes)
# ------------------------------------------------------------------

ENV_HUB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    ".env.hub",
)


def _strip_quotes(value: str) -> str:
    """Strip a matching leading/trailing quote pair from *value*."""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _load_env_hub(path: str) -> dict[str, str]:
    """Read ``.env.hub`` and return a ``dict`` of key/value pairs.

    Blank lines and lines starting with ``#`` are ignored.  The
    ``KEY="value"`` format is supported — surrounding quotes on the
    value are stripped.  The function does *not* overwrite existing
    environment variables — it only returns the parsed mapping so the
    caller can decide what to ``setdefault``.
    """
    mapping: dict[str, str] = {}
    if not os.path.isfile(path):
        return mapping
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = _strip_quotes(value).strip()
            if key:
                mapping[key] = value
    return mapping


class ExitCleaner(QObject):
    """Cleanup signals for graceful exit.

    Emits:
      - ``cleanup_finished()`` when all cleanup is done.
    """
    cleanup_finished = Signal()


def main() -> None:
    """Application entry point.

    - Loads ``.env.hub`` variables (without overwriting process env).
    - Initialises the Qt application.
    - Shows the ``MainWindow`` with a config dict derived from the hub.
    - Handles cleanup on shutdown and top-level errors gracefully.
    """
    # Load environment variables
    env_vars = _load_env_hub(ENV_HUB_PATH)
    # Apply defaults only if not already set in the process environment
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)

    # Build a config dict the MainWindow expects
    config = {k: v for k, v in env_vars.items()}

    # Initialize Qt application
    app = QApplication(sys.argv)
    window = MainWindow(config=config)
    window.setWindowTitle(config.get("APP_NAME", "Talib Video Studio"))

    # Add cleanup signals
    cleaner = ExitCleaner()
    cleaner.cleanup_finished.connect(app.quit)
    window.cleanup_finished.connect(cleaner.cleanup_finished.emit)

    # Show the window
    window.show()

    # Handle top-level errors
    def handle_top_level_error(exc_type, exc_value, exc_traceback):
        """Log and exit on top-level errors."""
        print(f"\n=== ERROR ===\nException type: {exc_type.__name__}\nValue: {exc_value}\nTraceback:\n{traceback.format_exc()}\n=====\nExiting gracefully...")
        cleaner.cleanup_finished.emit()
        app.exit(1)

    sys.excepthook = handle_top_level_error

    # Run the application
    try:
        app.exec()
    except Exception as exc:  # pragma: no cover
        handle_top_level_error(type(exc), exc, None)


if __name__ == "__main__":
    main()