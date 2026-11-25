"""Core export utilities, background thread, and optional export capabilities."""

from src.utils.ffmpeg import FFmpegExporter, ExportWorkerThread
from src.core.audio_mixer import (
    AudioMixSettings,
    build_audio_filter,
    build_loudness_filter,
    normalize_audio_settings,
)
from src.core.export_helpers import (
    build_ffmetadata_chapters,
    build_srt_document,
    sanitize_output_stem,
    sidecar_paths,
    write_sidecars,
)
from src.core.render_presets import (
    get_preset,
    list_presets,
    preset_choices,
    preset_to_export_settings,
)

__all__ = [
    "FFmpegExporter",
    "ExportWorkerThread",
    "AudioMixSettings",
    "build_audio_filter",
    "build_loudness_filter",
    "normalize_audio_settings",
    "build_ffmetadata_chapters",
    "build_srt_document",
    "sanitize_output_stem",
    "sidecar_paths",
    "write_sidecars",
    "get_preset",
    "list_presets",
    "preset_choices",
    "preset_to_export_settings",
]
