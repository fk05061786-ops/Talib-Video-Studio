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

from src.core.text_styles import TextStyle, build_drawtext, style_from_dict
from src.core.transitions import xfade_offsets
from src.core.grading import build_grade_filter, merge_grade, normalize_grade
from src.core.chroma import build_chroma_filter
from src.core.audio_mixer import (
    build_audio_filter,
    build_loudness_filter,
    normalize_audio_settings,
)
from src.core.export_helpers import write_sidecars
from src.core.export_validation import validate_export_request
from src.utils.packaging import resolve_binary

_XFADE_KINDS = {"crossfade": "fade", "dissolve": "dissolve"}


class FFmpegExporter:
    """Utility class that builds and runs an FFmpeg command.

    Parameters
    ----------
    ffmpeg_bin: str, optional
        Path to the ``ffmpeg`` executable. Defaults to ``"ffmpeg"`` which
        relies on the binary being in ``PATH``.
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        if str(ffmpeg_bin) in ("ffmpeg", "ffmpeg.exe"):
            self.ffmpeg_bin = resolve_binary("ffmpeg") or str(ffmpeg_bin)
        else:
            self.ffmpeg_bin = str(ffmpeg_bin)

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
        text_style: Optional[Any] = None,
        grade: Optional[Any] = None,
        chroma: Optional[Any] = None,
        audio_mix: Optional[Any] = None,
        loudnorm: bool = False,
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

        if audio_mix is not None:
            mix_filter = build_audio_filter(
                normalize_audio_settings(audio_mix),
                int(duration_sec * 1000) if duration_sec else None,
            )
            if mix_filter:
                a_filters.append(mix_filter)
        elif volume != 1.0:
            a_filters.append(f"volume={volume}")
        if loudnorm:
            a_filters.append(build_loudness_filter())

        # Chroma key and color grading (legacy brightness/contrast/saturation
        # remain supported and override the matching grading fields).
        chroma_filter = build_chroma_filter(chroma)
        if chroma_filter:
            v_filters.append(chroma_filter)

        if grade is not None:
            grade_settings = normalize_grade(grade)
            if brightness != 0.0 or contrast != 1.0 or saturation != 1.0:
                grade_settings = merge_grade(
                    grade_settings,
                    {
                        "brightness": brightness,
                        "contrast": contrast,
                        "saturation": saturation,
                    },
                )
        else:
            grade_settings = normalize_grade(
                {
                    "brightness": brightness,
                    "contrast": contrast,
                    "saturation": saturation,
                }
            )
        grade_filter = build_grade_filter(grade_settings)
        if grade_filter:
            v_filters.append(grade_filter)

        if opacity < 1.0:
            v_filters.append(f"format=rgba,colorchannelmixer=aa={opacity}")

        if scale != 1.0:
            v_filters.append(f"scale=iw*{scale}:ih*{scale}")

        if fade_in > 0:
            v_filters.append(f"fade=in:0:{int(fade_in*fps)}")
        if fade_out > 0 and duration_sec:
            v_filters.append(f"fade=out:{int(duration_sec*fps - fade_out*fps)}:{int(fade_out*fps)}")

        if text_style is not None:
            style = (
                style_from_dict(text_style)
                if isinstance(text_style, dict)
                else text_style
            )
            if isinstance(style, TextStyle) and style.text:
                v_filters.append(build_drawtext(style))
        elif text_overlay:
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
        transitions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Build a concat (or crossfade) command, skipping muted tracks."""
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

        # Filter complex for concatenation, with optional crossfades
        scale_spec = resolution.replace("x", ":")
        filter_parts = []
        for i, _ in enumerate(active_clips):
            filter_parts.append(
                f"[{i}:v]scale={scale_spec}:force_original_aspect_ratio=decrease,"
                f"pad={scale_spec}:(ow-iw)/2:(oh-ih)/2[v{i}];"
            )

        durations_ms = [
            int(float(clip.get("duration_sec", 0)) * 1000) for clip in active_clips
        ]
        transition_durations = [
            int(t.get("duration_ms", 0)) for t in (transitions or [])
        ]
        offsets = (
            xfade_offsets(durations_ms, transition_durations)
            if transitions
            else []
        )

        if offsets and len(offsets) == len(active_clips) - 1:
            last_v = "v0"
            last_a = "0:a"
            for index, (transition, offset) in enumerate(
                zip(transitions, offsets)
            ):
                duration = transition_durations[index] / 1000.0
                kind = _XFADE_KINDS.get(transition.get("kind", "crossfade"), "fade")
                filter_parts.append(
                    f"[{last_v}][v{index + 1}]xfade=transition={kind}:"
                    f"duration={duration:.3f}:offset={offset:.3f}[x{index}];"
                )
                filter_parts.append(
                    f"[{last_a}][{index + 1}:a]acrossfade=d={duration:.3f}:"
                    f"c1=tri:c2=tri[a{index}];"
                )
                last_v = f"x{index}"
                last_a = f"a{index}"
            filter_parts.append(f"[{last_v}]null[outv];")
            filter_parts.append(f"[{last_a}]anull[outa]")
        else:
            concat_v = "".join(f"[v{i}]" for i in range(len(active_clips)))
            concat_a = "".join(f"[{i}:a]" for i in range(len(active_clips)))
            filter_parts.append(
                f"{concat_v}concat=n={len(active_clips)}:v=1:a=0[outv];"
            )
            filter_parts.append(
                f"{concat_a}concat=n={len(active_clips)}:v=0:a=1[outa]"
            )

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
        text_style: Optional[Any] = None,
        grade: Optional[Any] = None,
        chroma: Optional[Any] = None,
        audio_mix: Optional[Any] = None,
        loudnorm: bool = False,
        subtitle_cues: Optional[Any] = None,
        chapter_markers: Optional[Any] = None,
    ) -> Tuple[bool, str]:
        """Run FFmpeg to export the video."""
        error = validate_export_request(input_path, output_path, self.ffmpeg_bin)
        if error is not None:
            return False, error
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Failed to create output directory: {exc}"

        cmd = self.build_command(
            input_path,
            output_path,
            resolution=resolution,
            fps=fps,
            start_sec=start_sec,
            duration_sec=duration_sec,
            speed=speed,
            volume=volume,
            fade_in=fade_in,
            fade_out=fade_out,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            opacity=opacity,
            scale=scale,
            text_overlay=text_overlay,
            text_style=text_style,
            grade=grade,
            chroma=chroma,
            audio_mix=audio_mix,
            loudnorm=loudnorm,
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
            try:
                sidecars = write_sidecars(
                    output_path, subtitle_cues, chapter_markers
                )
            except OSError as exc:
                return False, f"Export rendered but sidecar write failed: {exc}"
            message = "Export completed successfully."
            if sidecars:
                message += " Sidecars: " + ", ".join(path.name for path in sidecars)
            return True, message
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
        text_style: Optional[Any] = None,
        grade: Optional[Any] = None,
        chroma: Optional[Any] = None,
        audio_mix: Optional[Any] = None,
        loudnorm: bool = False,
        subtitle_cues: Optional[Any] = None,
        chapter_markers: Optional[Any] = None,
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
        self.speed = speed
        self.volume = volume
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.opacity = opacity
        self.scale = scale
        self.text_overlay = text_overlay
        self.text_style = text_style
        self.grade = grade
        self.chroma = chroma
        self.audio_mix = audio_mix
        self.loudnorm = loudnorm
        self.subtitle_cues = subtitle_cues
        self.chapter_markers = chapter_markers

    def run(self) -> None:
        success, message = self.exporter.export_video(
            self.input_path,
            self.output_path,
            resolution=self.resolution,
            fps=self.fps,
            start_sec=self.start_sec,
            duration_sec=self.duration_sec,
            speed=self.speed,
            volume=self.volume,
            fade_in=self.fade_in,
            fade_out=self.fade_out,
            brightness=self.brightness,
            contrast=self.contrast,
            saturation=self.saturation,
            opacity=self.opacity,
            scale=self.scale,
            text_overlay=self.text_overlay,
            text_style=self.text_style,
            grade=self.grade,
            chroma=self.chroma,
            audio_mix=self.audio_mix,
            loudnorm=self.loudnorm,
            subtitle_cues=self.subtitle_cues,
            chapter_markers=self.chapter_markers,
        )
        self.finished_export.emit(success, message)