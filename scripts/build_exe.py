"""Windows build script for Talib Video Studio.

Automates PyInstaller build process for creating a standalone Windows executable.
"""

import subprocess
import sys
from pathlib import Path

def build_windows_exe():
    """Build Windows executable using PyInstaller."""
    print("Building Talib Video Studio Windows executable...")

    # Install dependencies if needed
    print("Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Build the executable
    print("Running PyInstaller...")
    subprocess.run([
        sys.executable,
        "-m",
        "PyInstaller",
        "talib_video_studio.spec"
    ], check=True)

    print("Build complete! Check the 'dist' directory for the executable.")

if __name__ == "__main__":
    build_windows_exe()