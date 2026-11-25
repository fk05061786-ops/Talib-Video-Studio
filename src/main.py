"""Tal Video Studio — main entry point.

Loads ``.env.hub`` (repo root or PyInstaller bundle), resolves FFmpeg
binaries, applies the bundled stylesheet, and displays :class:`MainWindow`.
Top-level errors are logged to a file next to the working directory.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

# Ensure the project root is importable when launched as ``python src/main.py``.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.ui.main_window import MainWindow
from src.app.startup import init_effect_registry
from src.utils.packaging import bundle_dir, resolve_binary

logger = logging.getLogger(__name__)
ENV_HUB_PATH = os.path.join(_PROJECT_ROOT, ".env.hub")
ERROR_LOG_NAME = "talib_video_studio_error.log"


def _strip_quotes(value: str) -> str:
    """Strip a matching leading/trailing quote pair from *value*."""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _load_env_hub(path: str) -> dict[str, str]:
    """Read ``.env.hub`` and return a ``dict`` of key/value pairs.

    Blank lines and ``#`` comments are ignored; surrounding quotes on values
    are stripped. Existing environment variables are never overwritten.
    """
    mapping: dict[str, str] = {}
    if not os.path.isfile(path):
        return mapping
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = _strip_quotes(value).strip()
            if key:
                mapping[key] = value
    return mapping


def _find_env_hub() -> str:
    """Prefer the repo file, then the one bundled by PyInstaller."""
    candidates = (Path(ENV_HUB_PATH), bundle_dir() / ".env.hub")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ENV_HUB_PATH


def _write_error_log() -> str:
    """Append the current traceback to a log file and return its path."""
    path = Path.cwd() / ERROR_LOG_NAME
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
            handle.write("\n" + "=" * 60 + "\n")
    except OSError:
        return "<unwritable>"
    return str(path)


class ExitCleaner(QObject):
    """Cleanup signals for graceful exit."""

    cleanup_finished = Signal()


def main() -> None:
    """Application entry point."""
    env_vars = _load_env_hub(_find_env_hub())
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)

    config = dict(env_vars)
    config.setdefault("APP_NAME", "Talib Video Studio")
    for kind in ("ffmpeg", "ffprobe"):
        resolved = resolve_binary(kind, config)
        if resolved:
            key = f"{kind.upper()}_PATH"
            config[key] = resolved
            os.environ.setdefault(key, resolved)

    try:
        registry = init_effect_registry(config, extra_dir=bundle_dir() / "effects")
    except Exception:
        logger.exception("Effect registry initialization failed; starting empty")
        registry = None

    app = QApplication(sys.argv)
    theme_path = bundle_dir() / "src" / "ui" / "theme.qss"
    if theme_path.is_file():
        app.setStyleSheet(theme_path.read_text(encoding="utf-8"))

    window = MainWindow(config=config, registry=registry)
    window.setWindowTitle(config["APP_NAME"])

    cleaner = ExitCleaner()
    cleaner.cleanup_finished.connect(app.quit)
    window.cleanup_finished.connect(cleaner.cleanup_finished.emit)

    window.show()

    def handle_top_level_error(exc_type, exc_value, exc_traceback) -> None:
        """Log a fatal error, then shut down cleanly."""
        log_path = _write_error_log()
        print(
            f"\n=== ERROR ===\n{exc_type.__name__}: {exc_value}\n"
            f"Details written to: {log_path}\n=====\n"
        )
        cleaner.cleanup_finished.emit()
        app.exit(1)

    sys.excepthook = handle_top_level_error

    try:
        app.exec()
    except Exception as exc:  # pragma: no cover
        handle_top_level_error(type(exc), exc, None)


if __name__ == "__main__":
    main()
