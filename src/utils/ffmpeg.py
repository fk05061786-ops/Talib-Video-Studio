"""FFmpeg export utilities for Talib Video Studio.

Provides a thin wrapper around the ``ffmpeg`` CLI to export video files
with optional trimming, resolution scaling, effects, and frame‑rate conversion.
The heavy work runs in a ``QThread`` so the GUI stays responsive.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict

from PySide6.QtCore import QThread, Signal


class FFmpegExporter:
    """Utility class that builds and runs an FFmpeg command.

    Parameters
    ----------
    ffmpeg_bin: str, optional
        Path to the ``ffmpeg`` executable. Defaults to ``"ffmpeg"`` which
        relies on the binary being in ``PATH``.
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    # Command builder
    # ------------------------------------------------------------------
    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        resolution: str = "1920x1080",
        fps: int = 30,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        speed: float = 1.0,
        volume: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
        brightness: float = 0.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        opacity: float = 1.0,
        scale: float = 1.0,
        text_overlay: Optional[str] = None,
    ) -> List[str]:
        """Construct the FFmpeg CLI argument list."""
        try:
            target_w, target_h = map(int, resolution.lower().split("x"))
        except Exception:
            raise ValueError(f"Invalid resolution '{resolution}'")

        # Video filters
        v_filters = []
        # Audio filters
        a_filters = []

        if speed != 1.0:
            v_filters.append(f"setpts={1/speed}*PTS")
            a_filters.append(f"atempo={speed}")

        if volume != 1.0:
            a_filters.append(f"volume={volume}")

        # Color/Effects
        if brightness != 0.0 or contrast != 1.0 or saturation != 1.0:
            v_filters.append(f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}")

        if opacity < 1.0:
            v_filters.append(f"format=rgba,colorchannelmixer=aa={opacity}")

        if scale != 1.0:
            v_filters.append(f"scale=iw*{scale}:ih*{scale}")

        if fade_in > 0:
            v_filters.append(f"fade=in:0:{int(fade_in*fps)}")
        if fade_out > 0 and duration_sec:
            v_filters.append(f"fade=out:{int(duration_sec*fps - fade_out*fps)}:{int(fade_out*fps)}")

        if text_overlay:
            v_filters.append(f"drawtext=text='{text_overlay}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2")

        # Final Scale/Pad to target resolution
        v_filters.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease")
        v_filters.append(f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2")

        vf = ",".join(v_filters)
        af = ",".join(a_filters)

        cmd: List[str] = [self.ffmpeg_bin, "-y"]
        if start_sec is not None:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        cmd.extend(["-i", str(input_path)])
        if duration_sec is not None:
            cmd.extend(["-t", f"{duration_sec:.3f}"])

        cmd.extend(["-vf", vf])
        if a_filters:
            cmd.extend(["-af", af])

        cmd.extend([
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ])
        return cmd

    def build_concat_command(
        self,
        clips: List[Dict[str, Any]],
        output_path: Path,
        resolution: str = "1920x1080",
        fps: int = 30,
        muted_tracks: Optional[List[int]] = None,
    ) -> List[str]:
        """Build command to concatenate multiple clips with filters, skipping muted tracks."""
        # Filter clips by muted tracks
        active_clips = [
            c for c in clips
            if muted_tracks is None or c.get("track_index") not in muted_tracks
        ]
        if not active_clips:
            raise ValueError("No active clips to export (all tracks may be muted)")

        cmd: List[str] = [self.ffmpeg_bin, "-y"]

        # Inputs
        for clip in active_clips:
            if clip.get("start_sec") is not None:
                cmd.extend(["-ss", f"{clip['start_sec']:.3f}"])
            cmd.extend(["-i", str(clip["path"])])
            if clip.get("duration_sec") is not None:
                cmd.extend(["-t", f"{clip['duration_sec']:.3f}"])

        # Filter complex for concatenation
        filter_parts = []
        for i, _ in enumerate(active_clips):
            filter_parts.append(f"[{i}:v]scale={resolution.replace('x', ':')}:force_original_aspect_ratio=decrease,pad={resolution.replace('x', ':')}:(ow-iw)/2:(oh-ih)/2[v{i}];")

        concat_v = "".join(f"[v{i}]" for i in range(len(active_clips)))
        concat_a = "".join(f"[{i}:a]" for i in range(len(active_clips)))
        filter_parts.append(f"{concat_v}concat=n={len(active_clips)}:v=1:a=0[outv];")
        filter_parts.append(f"{concat_a}concat=n={len(active_clips)}:v=0:a=1[outa]")

        cmd.extend(["-filter_complex", "".join(filter_parts)])
        cmd.extend([
            "-map", "[outv]", "-map", "[outa]",
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ])
        return cmd

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def export_video(
        self,
        input_path: Path,
        output_path: Path,
        resolution: str = "1920x1080",
        fps: int = 30,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """Run FFmpeg to export the video."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Failed to create output directory: {exc}"

        cmd = self.build_command(
            input_path, output_path, resolution, fps, start_sec, duration_sec
        )
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return False, f"FFmpeg binary not found: '{self.ffmpeg_bin}'."
        except Exception as exc:
            return False, f"Unexpected error: {exc}"

        if result.returncode == 0:
            return True, "Export completed successfully."
        else:
            return False, result.stderr.strip() or "FFmpeg reported an error."


class ExportWorkerThread(QThread):
    """Runs FFmpeg export in a background thread."""

    finished_export = Signal(bool, str)

    def __init__(
        self,
        exporter: FFmpegExporter,
        input_path: Path,
        output_path: Path,
        resolution: str = "1920x1080",
        fps: int = 30,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.exporter = exporter
        self.input_path = input_path
        self.output_path = output_path
        self.resolution = resolution
        self.fps = fps
        self.start_sec = start_sec
        self.duration_sec = duration_sec

    def run(self) -> None:
        success, message = self.exporter.export_video(
            self.input_path,
            self.output_path,
            self.resolution,
            self.fps,
            self.start_sec,
            self.duration_sec,
        )
        self.finished_export.emit(success, message)