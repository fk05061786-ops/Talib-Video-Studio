"""Qt-free export helpers for subtitles, chapters, and filenames.

Provides utilities to generate SRT files, FFmpeg metadata chapter files,
and clean safe output paths/filenames without any Qt dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Union

from src.core.markers import Marker
from src.core.subtitles import SubtitleCue, format_srt_time


def build_srt_document(cues: Iterable[SubtitleCue]) -> str:
    """Build a complete, properly-formatted SRT file content from subtitle cues.

    Cues are sorted by start time and numbered sequentially starting at 1.
    """
    sorted_cues = sorted(cues, key=lambda c: c.start_ms)
    blocks: List[str] = []

    for index, cue in enumerate(sorted_cues, start=1):
        start_str = format_srt_time(cue.start_ms)
        end_str = format_srt_time(cue.end_ms)
        text = cue.text.strip()
        if cue.speaker:
            text = f"{cue.speaker}: {text}"
        block = f"{index}\n{start_str} --> {end_str}\n{text}"
        blocks.append(block)

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def escape_ffmetadata(val: str) -> str:
    """Escape special characters (=, ;, #, \\ and newline) for FFmpeg metadata."""
    out = str(val).replace("\\", "\\\\")
    out = out.replace("=", "\\=")
    out = out.replace(";", "\\;")
    out = out.replace("#", "\\#")
    out = out.replace("\n", "\\\n")
    return out


def build_ffmetadata_chapters(markers: Iterable[Marker]) -> str:
    """Build FFmpeg chapter metadata content from markers with duration.

    Ignores markers with 0 duration as they cannot form a valid chapter.
    """
    valid_chapters = [m for m in markers if m.duration_ms > 0]
    valid_chapters.sort(key=lambda m: m.time_ms)

    lines = [";FFMETADATA1"]
    for chapter in valid_chapters:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={chapter.time_ms}")
        lines.append(f"END={chapter.end_ms}")
        lines.append(f"title={escape_ffmetadata(chapter.label)}")

    return "\n".join(lines) + "\n"


def sanitize_output_stem(name: str, fallback: str = "export") -> str:
    """Sanitize a filename stem by removing unsafe characters and spaces.

    Replaces invalid characters with an underscore and collapses multiple underscores.
    """
    if not name or not name.strip():
        return fallback

    # Strip unwanted chars: allow alphanumeric, dash, and underscore
    cleaned = re.sub(r"[^\w\-.]", "_", name.strip())
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Strip leading/trailing dots or underscores
    cleaned = cleaned.strip("._")

    return cleaned if cleaned else fallback


def sidecar_paths(output_path: str | Path) -> tuple[Path, Path]:
    """Return ``(srt_path, ffmeta_path)`` beside a rendered video."""
    output = Path(output_path)
    stem = sanitize_output_stem(output.stem, fallback="export")
    return output.with_name(stem + ".srt"), output.with_name(stem + ".ffmeta")


def write_sidecars(
    output_path: str | Path,
    subtitle_cues: Optional[Iterable[SubtitleCue]] = None,
    chapter_markers: Optional[Iterable[Marker]] = None,
) -> List[Path]:
    """Write optional SRT/chapter sidecars; return paths actually written."""
    srt_path, ffmeta_path = sidecar_paths(output_path)
    written: List[Path] = []
    if subtitle_cues is not None:
        cues = list(subtitle_cues)
        if cues:
            srt_path.write_text(build_srt_document(cues), encoding="utf-8")
            written.append(srt_path)
    if chapter_markers is not None:
        markers = list(chapter_markers)
        if markers:
            ffmeta_path.write_text(
                build_ffmetadata_chapters(markers), encoding="utf-8"
            )
            written.append(ffmeta_path)
    return written
