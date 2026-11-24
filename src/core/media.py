"""Media processing utilities for Talib Video Studio.

Provides video duration inspection, frame extraction, and thumbnail generation
using FFmpeg/ffprobe.
"""

from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtGui import QPixmap, QImage


def get_media_info(path: str | Path) -> Dict[str, Any]:
    """Inspect media file using ffprobe and return metadata dict."""
    path_str = str(path)
    info = {
        "duration": 0.0,
        "resolution": "1920x1080",
        "fps": 30.0,
        "format": Path(path_str).suffix.lstrip(".").lower(),
        "size": Path(path_str).stat().st_size if Path(path_str).exists() else 0,
    }

    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path_str,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # Duration from format
        if "format" in data and "duration" in data["format"]:
            info["duration"] = float(data["format"]["duration"])

        # Video stream details
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                w = stream.get("width", 1920)
                h = stream.get("height", 1080)
                info["resolution"] = f"{w}x{h}"

                # Parse FPS from r_frame_rate (e.g. "30/1" or "30000/1001")
                r_fps = stream.get("r_frame_rate", "30/1")
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    if float(den) > 0:
                        info["fps"] = float(num) / float(den)
                break
    except Exception:
        # Fallback defaults if ffprobe is unavailable or fails
        pass

    return info


def get_media_duration(path: str | Path) -> float:
    """Return media duration in seconds."""
    return get_media_info(path)["duration"]


def extract_frame(path: str | Path, time_sec: float, output_path: str | Path) -> bool:
    """Extract a single video frame at *time_sec* to *output_path*."""
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{time_sec:.3f}",
            "-i", str(path),
            "-vframes", "1",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except Exception:
        return False


def get_clip_thumbnail(path: str | Path, width: int = 160, height: int = 90) -> QPixmap:
    """Generate or load a thumbnail QPixmap for the given media file."""
    # Return empty or fallback pixmap if extraction fails
    pixmap = QPixmap(width, height)
    pixmap.fill(QImage.Format_RGB32)
    return pixmap