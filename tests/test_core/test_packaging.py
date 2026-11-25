"""Headless tests for packaging and FFmpeg binary resolution helpers."""

import sys
import tempfile
import unittest
from pathlib import Path

from src.utils.packaging import (
    build_output_path,
    find_binary,
    pyinstaller_command,
    resolve_binary,
    validate_build_inputs,
)


def executable(path: Path) -> Path:
    path.touch()
    path.chmod(0o755)
    return path


class TestBinaryResolution(unittest.TestCase):
    def test_find_explicit_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = executable(Path(directory) / "ffmpeg.exe")
            self.assertEqual(
                find_binary(
                    "ffmpeg", explicit=str(binary), search_dirs=[], path_env=""
                ),
                str(binary),
            )

    def test_find_bundled_windows_name(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = executable(Path(directory) / "ffmpeg.exe")
            self.assertEqual(
                find_binary("ffmpeg.exe", search_dirs=[directory], path_env=""),
                str(binary),
            )

    def test_find_binary_on_path(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = executable(Path(directory) / "ffprobe")
            self.assertEqual(
                find_binary("ffprobe", path_env=directory), str(binary)
            )

    def test_missing_binary(self):
        self.assertIsNone(find_binary("definitely_missing_tool", path_env=""))

    def test_resolve_config_over_bundle_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            bundled = executable(root / "bin" / "ffmpeg")
            explicit = executable(root / "custom_ffmpeg")
            self.assertEqual(
                resolve_binary(
                    "ffmpeg",
                    {"FFMPEG_PATH": str(explicit)},
                    base_dir=root,
                    path_env="",
                ),
                str(explicit),
            )
            self.assertNotEqual(str(explicit), str(bundled))

    def test_resolve_bundled_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            bundled = executable(root / "bin" / "ffmpeg")
            self.assertEqual(
                resolve_binary("ffmpeg", base_dir=root, path_env=""),
                str(bundled),
            )

    def test_invalid_kind(self):
        self.assertIsNone(resolve_binary("not_a_tool"))


class TestBuildHelpers(unittest.TestCase):
    def test_validate_inputs_detects_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(validate_build_inputs(directory)), 5)

    def test_validate_inputs_complete(self):
        required = (
            "talib_video_studio.spec",
            "src/main.py",
            "src/ui/theme.qss",
            ".env.hub",
            "requirements.txt",
        )
        with tempfile.TemporaryDirectory() as directory:
            for name in required:
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertEqual(validate_build_inputs(directory), [])

    def test_pyinstaller_command(self):
        command = pyinstaller_command(Path("C:/project"))
        self.assertIn("--clean", command)
        self.assertTrue(command[-1].endswith("talib_video_studio.spec"))

    def test_output_path(self):
        path = build_output_path("C:/project")
        self.assertIn("dist", str(path))
        self.assertTrue(str(path).endswith("TalibVideoStudio.exe") or str(path).endswith("TalibVideoStudio"))

    def test_explicit_python_executable(self):
        command = pyinstaller_command(".")
        self.assertEqual(command[0], sys.executable)


if __name__ == "__main__":
    unittest.main()
