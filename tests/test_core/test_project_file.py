"""Headless tests for ``.tvs`` project save/load and validation."""

import json
import tempfile
import unittest
from pathlib import Path

from src.core.project_file import (
    PROJECT_EXTENSION,
    PROJECT_VERSION,
    ProjectDocument,
    ProjectError,
    deserialize_project,
    load_project,
    missing_media,
    project_path,
    save_project,
    serialize_project,
)
from src.core.timeline import TimelineManager
from src.core.undo import TimelineState, apply_state_to_manager, state_from_manager


def document() -> ProjectDocument:
    return ProjectDocument(
        name="Demo",
        timeline=TimelineState(
            clips=[
                {
                    "id": "v1",
                    "name": "clip.mp4",
                    "path": "media/clip.mp4",
                    "start": 0,
                    "duration": 5000,
                    "track_index": 1,
                },
                {
                    "id": "a1",
                    "name": "clip.mp4",
                    "path": "media/clip.mp4",
                    "start": 0,
                    "duration": 5000,
                    "track_index": 2,
                    "brightness": 0.2,
                },
            ],
            transitions=[
                {
                    "kind": "crossfade",
                    "duration_ms": 500,
                    "from_id": "a1",
                    "to_id": "a2",
                    "track_index": 2,
                }
            ],
            muted_tracks=[3],
            locked_tracks=[0],
        ),
        playhead_ms=1250,
        export_settings={"resolution": "1280x720", "fps": 24, "input_path": Path("media/clip.mp4")},
        text_style={"text": "Hello", "preset": "lower_third", "position": "bottom-left"},
        created_at="2026-01-01T00:00:00",
        modified_at="2026-01-02T00:00:00",
    )


class TestProjectSerialization(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "demo.tvs"
            ok, message = save_project(target, document())
            self.assertTrue(ok, message)
            loaded, info = load_project(target)
            self.assertIsNotNone(loaded, info)
            self.assertEqual(loaded.name, "Demo")
            self.assertEqual(loaded.playhead_ms, 1250)
            self.assertEqual(loaded.timeline.clips[1]["brightness"], 0.2)
            self.assertEqual(loaded.timeline.transitions[0]["kind"], "crossfade")
            self.assertEqual(loaded.timeline.muted_tracks, [3])
            self.assertEqual(loaded.timeline.locked_tracks, [0])
            self.assertEqual(loaded.export_settings["fps"], 24)
            self.assertEqual(loaded.export_settings["input_path"], "media/clip.mp4")
            self.assertEqual(loaded.text_style["preset"], "lower_third")

    def test_suffix_and_parent_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "demo"
            ok, message = save_project(target, document())
            self.assertTrue(ok, message)
            self.assertEqual(Path(message).suffix, PROJECT_EXTENSION)
            self.assertTrue(Path(message).is_file())

    def test_path_helper(self):
        self.assertEqual(project_path("demo").suffix, PROJECT_EXTENSION)
        self.assertEqual(project_path("demo.tvs").name, "demo.tvs")

    def test_unknown_fields_preserved(self):
        doc = document()
        doc.timeline.clips[0]["custom_effect"] = {"amount": 3}
        payload = serialize_project(doc)
        restored = deserialize_project(payload)
        self.assertEqual(restored.timeline.clips[0]["custom_effect"]["amount"], 3)

    def test_schema_version_in_payload(self):
        payload = serialize_project(document())
        self.assertEqual(payload["version"], PROJECT_VERSION)

    def test_version_validation(self):
        payload = serialize_project(document())
        payload["version"] = PROJECT_VERSION + 1
        with self.assertRaisesRegex(ProjectError, "newer"):
            deserialize_project(payload)
        payload["version"] = 0
        with self.assertRaisesRegex(ProjectError, "too old"):
            deserialize_project(payload)
        payload.pop("version")
        with self.assertRaises(ProjectError):
            deserialize_project(payload)

    def test_invalid_root_and_sections(self):
        with self.assertRaises(ProjectError):
            deserialize_project([1, 2, 3])
        payload = serialize_project(document())
        payload["timeline"] = "not-an-object"
        with self.assertRaises(ProjectError):
            deserialize_project(payload)
        payload = serialize_project(document())
        payload["timeline"]["clips"] = {"id": "x"}
        with self.assertRaises(ProjectError):
            deserialize_project(payload)

    def test_invalid_clips(self):
        payload = serialize_project(document())
        payload["timeline"]["clips"][0].pop("id")
        with self.assertRaisesRegex(ProjectError, "missing 'id'"):
            deserialize_project(payload)
        payload = serialize_project(document())
        payload["timeline"]["clips"][0]["duration"] = 0
        with self.assertRaises(ProjectError):
            deserialize_project(payload)
        payload = serialize_project(document())
        payload["timeline"]["clips"][0]["start"] = "oops"
        with self.assertRaises(ProjectError):
            deserialize_project(payload)

    def test_invalid_transitions_and_track_flags(self):
        payload = serialize_project(document())
        payload["timeline"]["transitions"][0].pop("kind")
        with self.assertRaisesRegex(ProjectError, "missing 'kind'"):
            deserialize_project(payload)
        payload = serialize_project(document())
        payload["timeline"]["locked_tracks"] = ["oops"]
        with self.assertRaises(ProjectError):
            deserialize_project(payload)

    def test_export_and_text_sections_must_be_objects(self):
        payload = serialize_project(document())
        payload["export_settings"] = 5
        with self.assertRaises(ProjectError):
            deserialize_project(payload)
        payload = serialize_project(document())
        payload["text_style"] = "nope"
        with self.assertRaises(ProjectError):
            deserialize_project(payload)


class TestProjectFileErrors(unittest.TestCase):
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            result, message = load_project(Path(directory) / "missing.tvs")
            self.assertIsNone(result)
            self.assertIn("not found", message)

    def test_directory_instead_of_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "folder.tvs"
            folder.mkdir()
            result, message = load_project(folder)
            self.assertIsNone(result)
            self.assertIn("not a file", message)

    def test_corrupt_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.tvs"
            target.write_text("{broken json", encoding="utf-8")
            result, message = load_project(target)
            self.assertIsNone(result)
            self.assertIn("Corrupt", message)

    def test_invalid_schema_from_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.tvs"
            target.write_text(json.dumps({"version": 99}), encoding="utf-8")
            result, message = load_project(target)
            self.assertIsNone(result)
            self.assertIn("newer", message)

    def test_missing_media_reported_without_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "demo.tvs"
            save_project(target, document())
            loaded, message = load_project(target)
            self.assertIsNotNone(loaded)
            self.assertIn("missing", message)

    def test_relative_media_resolved_against_project(self):
        doc = document()
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "media"
            media.mkdir()
            (media / "clip.mp4").write_bytes(b"video")
            self.assertEqual(missing_media(doc, directory), [])
            self.assertEqual(len(missing_media(doc)), 2)

    def test_save_rejects_invalid_document(self):
        doc = document()
        doc.timeline.clips[0]["duration"] = 0
        with tempfile.TemporaryDirectory() as directory:
            ok, message = save_project(Path(directory) / "bad.tvs", doc)
            self.assertFalse(ok)
            self.assertTrue(message)

    def test_manager_state_round_trip_through_project(self):
        manager = TimelineManager()
        item = manager.add_clip_to_track("c1", "clip", 0, 0, 1000)
        item.brightness = 0.7
        manager.tracks[0].is_muted = True
        doc = ProjectDocument(timeline=state_from_manager(manager))

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "state.tvs"
            save_project(target, doc)
            loaded, message = load_project(target)
            self.assertIsNotNone(loaded, message)

        restored = TimelineManager()
        apply_state_to_manager(loaded.timeline, restored)
        self.assertEqual(state_from_manager(restored), state_from_manager(manager))


if __name__ == "__main__":
    unittest.main()
