"""Headless tests for Phase 2F preset, audio and sidecar wiring."""

import sys
import tempfile
import types
import unittest
from pathlib import Path

from src.core.audio_mixer import (
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
from src.core.markers import Marker
from src.core.render_presets import (
    get_preset,
    list_presets,
    preset_choices,
    preset_to_export_settings,
)
from src.core.subtitles import SubtitleCue


if "PySide6.QtCore" not in sys.modules:
    qt_core = types.ModuleType("PySide6.QtCore")

    class _QThread:
        def __init__(self, parent=None):
            pass

    class _Signal:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

    qt_core.QThread = _QThread
    qt_core.Signal = _Signal
    qt_package = types.ModuleType("PySide6")
    qt_package.QtCore = qt_core
    sys.modules["PySide6"] = qt_package
    sys.modules["PySide6.QtCore"] = qt_core

from src.core.export import (  # noqa: E402
    FFmpegExporter,
    build_audio_filter as exported_build_audio_filter,
    list_presets as exported_list_presets,
    write_sidecars as exported_write_sidecars,
)


class TestRenderPresets(unittest.TestCase):
    def test_catalog(self):
        choices = preset_choices()
        self.assertEqual(choices["Custom"], None)
        self.assertEqual(choices[list_presets()["youtube_1080p_60"]], "youtube_1080p_60")
        self.assertIsNotNone(get_preset("shorts_9_16"))

    def test_preset_to_settings(self):
        settings = preset_to_export_settings("youtube_1080p_60")
        self.assertEqual(settings["resolution"], "1920x1080")
        self.assertEqual(settings["fps"], 60)
        self.assertEqual(settings["video_bitrate"], "15M")
        shorts = preset_to_export_settings("shorts_9_16")
        self.assertEqual(shorts["resolution"], "1080x1920")
        self.assertIsNone(preset_to_export_settings("unknown"))


class TestAudioMixerWiring(unittest.TestCase):
    def test_settings_normalization(self):
        mix = normalize_audio_settings({"gain_db": 99, "fade_in_ms": -5})
        self.assertEqual(mix.gain_db, 12)
        self.assertEqual(mix.fade_in_ms, 0)

    def test_audio_filter_chain(self):
        mix = normalize_audio_settings(
            {"gain_db": -6, "fade_in_ms": 500, "fade_out_ms": 1000}
        )
        chain = build_audio_filter(mix, duration_ms=5000)
        self.assertIn("volume=", chain)
        self.assertIn("afade=t=in:st=0:d=0.500", chain)
        self.assertIn("afade=t=out:st=4.000:d=1.000", chain)
        self.assertEqual(
            build_loudness_filter(), "loudnorm=I=-23.0:TP=-1.0:LRA=11"
        )

    def test_ffmpeg_command_audio_filters(self):
        exporter = FFmpegExporter("ffmpeg")
        command = exporter.build_command(
            Path("in.mp4"),
            Path("out.mp4"),
            audio_mix={"gain_db": 6, "mute": False, "fade_in_ms": 250},
            loudnorm=True,
        )
        audio_filters = command[command.index("-af") + 1]
        self.assertIn("volume=", audio_filters)
        self.assertIn("afade=t=in:st=0:d=0.250", audio_filters)
        self.assertIn("loudnorm=", audio_filters)


class TestSidecarHelpers(unittest.TestCase):
    def test_sanitize_and_paths(self):
        self.assertEqual(sanitize_output_stem("My Clip!-01"), "My_Clip_-01")
        self.assertEqual(sanitize_output_stem("   "), "export")
        srt, ffmeta = sidecar_paths("C:/out/My Clip.mp4")
        self.assertEqual(srt.name, "My_Clip.srt")
        self.assertEqual(ffmeta.name, "My_Clip.ffmeta")

    def test_documents(self):
        cues = [SubtitleCue(1000, 2500, "Hello", speaker="Ann")]
        srt = build_srt_document(cues)
        self.assertIn("00:00:01,000 --> 00:00:02,500", srt)
        self.assertIn("Ann: Hello", srt)
        chapter = Marker(0, "Intro", duration_ms=2000)
        meta = build_ffmetadata_chapters([chapter])
        self.assertIn(";FFMETADATA1", meta)
        self.assertIn("END=2000", meta)

    def test_write_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "demo.mp4"
            written = write_sidecars(
                output,
                subtitle_cues=[SubtitleCue(0, 1000, "Hi")],
                chapter_markers=[Marker(0, "Start", duration_ms=1000)],
            )
            self.assertEqual(len(written), 2)
            self.assertTrue(written[0].is_file())
            self.assertTrue(written[1].is_file())

    def test_core_export_reexports(self):
        self.assertIs(exported_build_audio_filter, build_audio_filter)
        self.assertIs(exported_list_presets, list_presets)
        self.assertIs(exported_write_sidecars, write_sidecars)


if __name__ == "__main__":
    unittest.main()
