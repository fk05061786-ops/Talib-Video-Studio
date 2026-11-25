"""Windows build script for Talib Video Studio.

Validates inputs, ensures PyInstaller is available, and runs the spec file
from the project root. Run from anywhere with::

    python scripts/build_exe.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.packaging import (
    build_output_path,
    pyinstaller_command,
    validate_build_inputs,
)


def build_windows_exe() -> bool:
    """Build the standalone executable; return ``True`` on success."""
    print(f"Project root: {ROOT}")
    missing = validate_build_inputs(ROOT)
    if missing:
        print("Cannot build — missing required files:")
        for name in missing:
            print(f"  - {name}")
        return False

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            print("Failed to install PyInstaller.")
            return False

    command = pyinstaller_command(ROOT)
    print("Running: " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(f"PyInstaller failed with exit code {result.returncode}.")
        return False

    executable = build_output_path(ROOT)
    if not executable.exists():
        print(f"Build finished but no executable was found at {executable}")
        return False
    print(f"Build complete: {executable}")
    return True


def main() -> int:
    return 0 if build_windows_exe() else 1


if __name__ == "__main__":
    raise SystemExit(main())
