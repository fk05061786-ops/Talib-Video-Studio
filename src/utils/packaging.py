"""Qt-free helpers for Windows packaging and FFmpeg binary resolution."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def bundle_dir() -> Path:
    """Return the PyInstaller extraction directory or the project root."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    """Return whether the app is running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def _candidate_names(name: str) -> List[str]:
    names = [name]
    if os.name == "nt" and not name.lower().endswith(".exe"):
        names.append(name + ".exe")
    return names


def find_binary(
    name: str,
    explicit: Optional[str | Path] = None,
    search_dirs: Optional[Iterable[str | Path]] = None,
    path_env: Optional[str] = None,
) -> Optional[str]:
    """Locate an executable: explicit path, bundled dirs, then ``PATH``."""
    candidates: List[str] = []
    if explicit:
        candidates.append(str(explicit))
    for directory in search_dirs or ():
        for candidate in _candidate_names(name):
            candidates.append(str(Path(directory) / candidate))

    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    env = path_env if path_env is not None else os.environ.get("PATH", "")
    for candidate in _candidate_names(name):
        found = shutil.which(candidate, path=env)
        if found:
            return found
    return None


def resolve_binary(
    kind: str,
    config: Optional[Dict[str, str]] = None,
    base_dir: Optional[str | Path] = None,
    path_env: Optional[str] = None,
) -> Optional[str]:
    """Resolve ``ffmpeg`` or ``ffprobe`` using config, env, bundle, then PATH."""
    if kind not in ("ffmpeg", "ffprobe"):
        return None
    config = config or {}
    key = f"{kind.upper()}_PATH"
    explicit = config.get(key) or os.environ.get(key)
    root = Path(base_dir) if base_dir else bundle_dir()
    return find_binary(
        kind,
        explicit=explicit,
        search_dirs=(root / "bin", root),
        path_env=path_env,
    )


def validate_build_inputs(root: str | Path) -> List[str]:
    """Return required build files that are missing under *root*."""
    required = (
        "talib_video_studio.spec",
        "src/main.py",
        "src/ui/theme.qss",
        ".env.hub",
        "requirements.txt",
    )
    root_path = Path(root)
    return [name for name in required if not (root_path / name).is_file()]


def pyinstaller_command(
    root: str | Path, spec_name: str = "talib_video_studio.spec", clean: bool = True
) -> List[str]:
    """Build the PyInstaller CLI argument list."""
    command = [sys.executable, "-m", "PyInstaller"]
    if clean:
        command.append("--clean")
    command.append(str(Path(root) / spec_name))
    return command


def build_output_path(
    root: str | Path, name: str = "TalibVideoStudio"
) -> Path:
    """Return the expected executable path for a successful build."""
    folder = Path(root) / "dist" / name
    return folder / (name + ".exe") if os.name == "nt" else folder / name
