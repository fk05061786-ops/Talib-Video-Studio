"""Headless tests for grading, chroma key, proxy helpers and FFmpeg filters."""

import sys
import tempfile
import types
import unittest
from pathlib import Path

from src.core.chroma import (
    CHROMA_PRESETS,
    build_chroma_filter,
    ffmpeg_color,
    normalize_chroma,
)
from src.core.grading import (
    build_grade_filter,
    merge_grade,
    normalize_grade,
)
from src.core.proxy import (
    ProxyManager,
    build_proxy_command,
    generate_proxy,
    normalize_proxy,
    proxy_path_for,
)


# Minimal Qt stub so the FFmpeg builder can be imported without PySide6/display.
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


from src.utils.ffmpeg import FFmpegExporter  # noqa: E402


class TestGrading(unittest.TestCase):
    def test_normalization_clamps(self):
        grade = normalize_grade(
            {"brightness": 9, "contrast": -1, "saturation": 5, "vibrance": -9,
             "warmth": 4, "tint": -4}
        )
        self.assertEqual(grade.brightness, 1)
        self.assertEqual(grade.contrast, 0)
        self.assertEqual(grade.saturation, 2)
        self.assertEqual(grade.vibrance, -1)
        self.assertEqual(grade.warmth, 1)
        self.assertEqual(grade.tint, -1)

    def test_default_filter_is_empty(self):
        self.assertEqual(build_grade_filter(), "")

    def test_eq_filter(self):
        text = build_grade_filter({"brightness": 0.2, "contrast": 1.1})
        self.assertIn("eq=brightness=0.2:contrast=1.1:saturation=1.0", text)

    def test_vibrance_and_color_balance(self):
        text = build_grade_filter({"vibrance": 0.3, "warmth": 0.5, "tint": -0.4})
        self.assertIn("vibrance=intensity=0.3", text)
        self.assertIn("colorbalance=rm=0.5:bm=-0.5:gm=-0.4", text)

    def test_merge_grade(self):
        merged = merge_grade(normalize_grade({"contrast": 1.2}), {"brightness": 0.1})
        self.assertEqual(merged.contrast, 1.2)
        self.assertEqual(merged.brightness, 0.1)


class TestChromaKey(unittest.TestCase):
    def test_presets_and_colors(self):
        self.assertIn("green_screen", CHROMA_PRESETS)
        self.assertEqual(ffmpeg_color("green"), "0x00FF00")
        self.assertEqual(ffmpeg_color("#ff00aa"), "0xFF00AA")
        self.assertEqual(ffmpeg_color("nonsense"), "0x00FF00")

    def test_filter_disabled(self):
        self.assertEqual(build_chroma_filter({"enabled": False}), "")

    def test_filter_enabled(self):
        text = build_chroma_filter(
            {"enabled": True, "color": "blue", "similarity": 0.3, "blend": 0.1}
        )
        self.assertEqual(
            text,
            "chromakey=color=0x0000FF:similarity=0.3:blend=0.1",
        )

    def test_normalization_clamps(self):
        settings = normalize_chroma(
            {"enabled": True, "similarity": 5, "blend": -1}
        )
        self.assertEqual(settings.similarity, 1.0)
        self.assertEqual(settings.blend, 0.0)


class TestProxyHelpers(unittest.TestCase):
    def test_path_for(self):
        source = Path("media/clip.mp4")
        self.assertEqual(
            proxy_path_for(source), Path("media/proxies/clip_proxy.mp4")
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cache"
            self.assertEqual(
                proxy_path_for(source, target), target / "clip_proxy.mp4"
            )

    def test_command(self):
        command = build_proxy_command("in.mp4", "out.mp4", "960x540", "ffmpeg")
        self.assertEqual(command[0], "ffmpeg")
        self.assertIn("scale=960:540", command)
        self.assertIn("ultrafast", command)
        with self.assertRaises(ValueError):
            build_proxy_command("in.mp4", "out.mp4", "bad")

    def test_generate_proxy_missing_source(self):
        ok, message = generate_proxy("missing.mp4", "proxy.mp4")
        self.assertFalse(ok)
        self.assertIn("not found", message)

    def test_normalization(self):
        settings = normalize_proxy({"enabled": True, "scale": 9})
        self.assertEqual(settings.scale, 1.0)

    def test_manager_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "clip.mp4"
            source.write_bytes(b"video")
            proxy = proxy_path_for(source)
            proxy.parent.mkdir(parents=True, exist_ok=True)
            proxy.write_bytes(b"proxy")
            manager = ProxyManager({"enabled": False, "folder": "proxies"})
            self.assertEqual(manager.resolve(source), source)
            self.assertEqual(manager.path_for(source), proxy)
            manager.set_settings({"enabled": True, "folder": "proxies"})
            self.assertEqual(manager.resolve(source), proxy)
            ok, message = manager.ensure(source)
            self.assertTrue(ok)
            self.assertEqual(message, str(proxy))


class TestFFmpegCommandGeneration(unittest.TestCase):
    def setUp(self):
        self.exporter = FFmpegExporter("ffmpeg")

    def command(self, **kwargs):
        return self.exporter.build_command(
            Path("in.mp4"), Path("out.mp4"), **kwargs
        )

    def video_filter(self, command):
        return command[command.index("-vf") + 1]

    def test_legacy_brightness_still_generates_eq(self):
        vf = self.video_filter(self.command(brightness=0.2))
        self.assertIn("eq=brightness=0.2:contrast=1.0:saturation=1.0", vf)

    def test_grade_and_chroma_in_filter_chain(self):
        command = self.command(
            grade={"brightness": 0.1, "vibrance": 0.2},
            chroma={"enabled": True, "color": "green", "similarity": 0.2, "blend": 0.05},
        )
        vf = self.video_filter(command)
        self.assertLess(vf.index("chromakey="), vf.index("eq="))
        self.assertIn("vibrance=intensity=0.2", vf)

    def test_legacy_grade_overrides_grade_dict(self):
        vf = self.video_filter(
            self.command(
                grade={"brightness": 0.9}, brightness=0.1, contrast=1.3
            )
        )
        self.assertIn("brightness=0.1:contrast=1.3", vf)
        self.assertNotIn("brightness=0.9", vf)

    def test_disabled_chroma_absent(self):
        vf = self.video_filter(self.command(chroma={"enabled": False}))
        self.assertNotIn("chromakey", vf)


if __name__ == "__main__":
    unittest.main()
