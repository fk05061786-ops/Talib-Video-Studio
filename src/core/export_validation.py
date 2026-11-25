"""Qt-free validation for export requests before invoking FFmpeg."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.utils.packaging import find_binary


def validate_export_request(
    input_path: Optional[str | Path],
    output_path: Optional[str | Path],
    ffmpeg_bin: Optional[str | Path] = None,
) -> Optional[str]:
    """Return a human-readable error, or ``None`` when the request is valid."""
    if not input_path:
        return "No input media selected."
    source = Path(input_path)
    if not source.is_file():
        return f"Input media not found: {source}"
    if source.stat().st_size == 0:
        return f"Input media is empty: {source}"

    if not output_path:
        return "No output path specified."
    destination = Path(output_path)
    if destination.exists() and destination.is_dir():
        return f"Output path is a directory: {destination}"
    try:
        if source.resolve() == destination.resolve():
            return "Output path must differ from input path."
    except OSError:
        pass

    if ffmpeg_bin and find_binary(str(ffmpeg_bin)) is None:
        return f"FFmpeg binary not found: {ffmpeg_bin}"
    return None
