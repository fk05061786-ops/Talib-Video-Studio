"""Headless unit tests for the Qt-free :class:`EffectRegistry` and
:class:`EffectMetadata`.

All tests run without PySide6 or a display — they import only standard‑library
and the project's own Qt‑free modules.
"""

import unittest
from dataclasses import dataclass
from typing import Any

from src.core.effects_registry import (
    EffectMetadata,
    RegisteredEffect,
    EffectRegistry,
)


# ------------------------------------------------------------------
# Dummy effect classes used across test methods
# ------------------------------------------------------------------

@dataclass
class SimpleVideoEffect:
    """A minimal video effect module."""

    brightness: float = 1.0
    contrast: float = 1.0


@dataclass
class SimpleAudioEffect:
    """A minimal audio effect module."""

    gain_db: float = 0.0


@dataclass
class SimpleTransitionEffect:
    """A minimal transition effect module."""

    kind: str = "crossfade"


@dataclass
class SimpleTextEffect:
    """A minimal text effect module."""

    text: str = ""
    font_size: int = 48


# ------------------------------------------------------------------
# Test suite
# ------------------------------------------------------------------


class TestEffectMetadata(unittest.TestCase):
    """Tests for :class:`EffectMetadata` dataclass."""

    def test_defaults(self):
        md = EffectMetadata(name="test", category="video")
        self.assertEqual(md.category, "video")
        self.assertEqual(md.version, "0.1.0")
        self.assertEqual(md.description, "")
        self.assertEqual(md.tags, ())
        self.assertEqual(md.author, "")
        self.assertEqual(md.required_binaries, ())
        self.assertEqual(md.min_fps, 0.0)
        self.assertIsNone(md.max_fps)
        self.assertTrue(md.supports_trim)
        self.assertTrue(md.supports_speed)

    def test_custom_values(self):
        md = EffectMetadata(
            name="my-transition",
            category="transition",
            version="2.0.0",
            description="A wipe transition",
            tags=("wipe", "horizontal"),
            author="Jane Doe",
            required_binaries=("ffmpeg",),
            min_fps=24.0,
            max_fps=60.0,
            supports_trim=False,
            supports_speed=False,
        )
        self.assertEqual(md.name, "my-transition")
        self.assertEqual(md.category, "transition")
        self.assertEqual(md.version, "2.0.0")
        self.assertEqual(md.description, "A wipe transition")
        self.assertEqual(md.tags, ("wipe", "horizontal"))
        self.assertEqual(md.author, "Jane Doe")
        self.assertEqual(md.required_binaries, ("ffmpeg",))
        self.assertEqual(md.min_fps, 24.0)
        self.assertEqual(md.max_fps, 60.0)
        self.assertFalse(md.supports_trim)
        self.assertFalse(md.supports_speed)

    def test_matches_tag(self):
        md = EffectMetadata(name="t", category="video", tags=("fade", "audio"))
        self.assertTrue(md.matches_tag("fade"))
        self.assertTrue(md.matches_tag("audio"))
        self.assertFalse(md.matches_tag("wipe"))
        self.assertFalse(md.matches_tag(""))


class TestRegisteredEffect(unittest.TestCase):
    """Tests for :class:`RegisteredEffect` dataclass."""

    def test_creation(self):
        reg = RegisteredEffect(
            name="test-effect",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="test-effect", category="video"),
        )
        self.assertEqual(reg.name, "test-effect")
        self.assertIs(reg.cls, SimpleVideoEffect)
        self.assertIsInstance(reg.metadata, EffectMetadata)


class TestEffectRegistry(unittest.TestCase):
    """Tests for the core :class:`EffectRegistry`. Registry-level — no Qt
    dependency, fully head‑testable."""

    def setUp(self):
        self.registry = EffectRegistry()

    def test_empty_registry(self):
        self.assertEqual(len(self.registry.list_all()), 0)
        self.assertEqual(self.registry.has("anything"), False)
        self.assertEqual(self.registry.get_by_category("video"), [])
        self.assertEqual(self.registry.get_by_tag("anytag"), [])

    def test_register_and_has(self):
        self.registry.register(
            name="brightness-up",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(
                name="brightness-up",
                category="video",
                description="Increases brightness",
                tags=("video", "brightness"),
            ),
        )
        self.assertTrue(self.registry.has("brightness-up"))

    def test_register_duplicate_raises(self):
        self.registry.register(
            name="dup",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="dup", category="video"),
        )
        with self.assertRaises(ValueError):
            self.registry.register(
                name="dup",
                cls=SimpleVideoEffect,
                metadata=EffectMetadata(name="dup", category="audio"),
            )

    def test_get_returns_registered(self):
        self.registry.register(
            name="my-transition",
            cls=SimpleTransitionEffect,
            metadata=EffectMetadata(name="my-transition", category="transition"),
        )
        reg = self.registry.get("my-transition")
        self.assertEqual(reg.name, "my-transition")
        self.assertIs(reg.cls, SimpleTransitionEffect)

    def test_get_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.registry.get("nonexistent")

    def test_get_by_category(self):
        self.registry.register(
            name="vid1",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="vid1", category="video", tags=("video",)),
        )
        self.registry.register(
            name="aud1",
            cls=SimpleAudioEffect,
            metadata=EffectMetadata(name="aud1", category="audio", tags=("audio",)),
        )
        self.registry.register(
            name="trans1",
            cls=SimpleTransitionEffect,
            metadata=EffectMetadata(name="trans1", category="transition", tags=("transition",)),
        )

        video_effects = self.registry.get_by_category("video")
        self.assertEqual(len(video_effects), 1)
        self.assertEqual(video_effects[0].name, "vid1")

        audio_effects = self.registry.get_by_category("audio")
        self.assertEqual(len(audio_effects), 1)
        self.assertEqual(audio_effects[0].name, "aud1")

        transition_effects = self.registry.get_by_category("transition")
        self.assertEqual(len(transition_effects), 1)
        self.assertEqual(transition_effects[0].name, "trans1")

        # Non-existent category returns empty list
        empty = self.registry.get_by_category("nonexistent")
        self.assertEqual(len(empty), 0)

    def test_get_by_tag(self):
        self.registry.register(
            name="t1",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="t1", category="video", tags=("fade", "video")),
        )
        self.registry.register(
            name="t2",
            cls=SimpleAudioEffect,
            metadata=EffectMetadata(name="t2", category="audio", tags=("fade", "audio")),
        )
        self.registry.register(
            name="t3",
            cls=SimpleTransitionEffect,
            metadata=EffectMetadata(name="t3", category="transition", tags=("wipe",)),
        )

        fade_video = self.registry.get_by_tag("fade")
        self.assertEqual(len(fade_video), 2)
        names = [r.name for r in fade_video]
        self.assertIn("t1", names)
        self.assertIn("t2", names)

        fade_tag = self.registry.get_by_tag("fade")
        self.assertEqual(len(fade_tag), 2)

        wipe_only = self.registry.get_by_tag("wipe")
        self.assertEqual(len(wipe_only), 1)
        self.assertEqual(wipe_only[0].name, "t3")

        # Non-existent tag returns empty list
        empty = self.registry.get_by_tag("nonexistent")
        self.assertEqual(len(empty), 0)

    def test_filter_by_categories(self):
        self.registry.register(
            name="v1",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="v1", category="video", tags=("a",)),
        )
        self.registry.register(
            name="v2",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="v2", category="video", tags=("b",)),
        )
        self.registry.register(
            name="a1",
            cls=SimpleAudioEffect,
            metadata=EffectMetadata(name="a1", category="audio", tags=("a",)),
        )

        # Single category
        video = self.registry.filter_by_categories("video")
        self.assertEqual(len(video), 2)

        # Multiple categories
        video_audio = self.registry.filter_by_categories("video", "audio")
        self.assertEqual(len(video_audio), 3)  # v1, v2, a1

    def test_filter_by_tags(self):
        self.registry.register(
            name="t1",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="t1", category="video", tags=("x", "y")),
        )
        self.registry.register(
            name="t2",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="t2", category="video", tags=("x",)),
        )
        self.registry.register(
            name="t3",
            cls=SimpleAudioEffect,
            metadata=EffectMetadata(name="t3", category="audio", tags=("x",)),
        )

        # All given tags (x AND y)
        xy = self.registry.filter_by_tags("x", "y")
        self.assertEqual(len(xy), 1)
        self.assertEqual(xy[0].name, "t1")

        # Any one tag
        x_only = self.registry.filter_by_tags("x")
        self.assertEqual(len(x_only), 3)  # t1, t2, t3

        # Single tag arg works like get_by_tag
        single = self.registry.filter_by_tags("x")
        self.assertEqual(len(single), 3)

    def test_validate_module(self):
        self.registry.register(
            name="valid-effect",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="valid-effect", category="video"),
        )
        error = self.registry.validate_module("valid-effect")
        self.assertIsNone(error)

    def test_validate_unknown(self):
        error = self.registry.validate_module("no-such-effect")
        self.assertIn("not registered", error)

    def test_validate_all(self):
        self.registry.register(
            name="good",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="good", category="video"),
        )
        self.registry.register(
            name="bad",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(name="bad", category="video"),
        )
        # "bad" is still valid at registry level
        results = self.registry.validate_all()
        self.assertEqual(len(results), 2)
        self.assertIsNone(results["good"])
        self.assertIsNone(results["bad"])

    def test_filter_by_tag_empty_tag_returns_all(self):
        """filter_by_tags with no args should return all registered modules."""
        self.registry.register("a", cls=SimpleVideoEffect, metadata=EffectMetadata(name="a", category="video"))
        self.registry.register("b", cls=SimpleAudioEffect, metadata=EffectMetadata(name="b", category="audio"))
        all_mods = self.registry.filter_by_tags()
        self.assertEqual(len(all_mods), 2)

    def test_contains_and_getitem(self):
        self.registry.register(
            name="lookup",
            cls=SimpleTransitionEffect,
            metadata=EffectMetadata(name="lookup", category="transition"),
        )
        self.assertIn("lookup", self.registry)
        reg = self.registry["lookup"]
        self.assertEqual(reg.name, "lookup")

    def test_list_all_returns_copy(self):
        self.registry.register("one", cls=SimpleVideoEffect, metadata=EffectMetadata(name="one", category="video"))
        regs = self.registry.list_all()
        self.assertEqual(len(regs), 1)
        # Modifying the returned list should not affect the registry
        regs.clear()
        self.assertEqual(len(self.registry.list_all()), 1)

    def test_module_with_tags_and_category_filter(self):
        """Modules registered with tags should be findable both by category and by tag."""
        self.registry.register(
            name="vid-transition",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(
                name="vid-transition",
                category="video",
                tags=("transition",),
            ),
        )
        # Should appear under category "video"
        video = self.registry.filter_by_categories("video")
        self.assertEqual(len(video), 1)
        self.assertEqual(video[0].name, "vid-transition")
        # Should appear under tag "transition"
        by_tag = self.registry.filter_by_tag("transition")
        self.assertEqual(len(by_tag), 1)
        self.assertEqual(by_tag[0].name, "vid-transition")


class TestEffectRegistryIntegration(unittest.TestCase):
    """Integration‑style tests that use the registry with dummy effect classes."""

    def test_full_lifecycle(self):
        """Register → lookup → filter → validate → list → contains."""
        registry = EffectRegistry()

        # Register four modules across categories
        registry.register(
            "exposure",
            cls=SimpleVideoEffect,
            metadata=EffectMetadata(
                name="exposure",
                category="video",
                description="Exposure adjustment",
                tags=("color", "exposure"),
            ),
        )
        registry.register(
            "compressor",
            cls=SimpleAudioEffect,
            metadata=EffectMetadata(
                name="compressor",
                category="audio",
                description="Dynamic range compression",
                tags=("dynamic", "compressor"),
            ),
        )
        registry.register(
            "wipe",
            cls=SimpleTransitionEffect,
            metadata=EffectMetadata(
                name="wipe",
                category="transition",
                description="Horizontal wipe",
                tags=("wipe", "horizontal"),
            ),
        )
        registry.register(
            "lower-third",
            cls=SimpleTextEffect,
            metadata=EffectMetadata(
                name="lower-third",
                category="text",
                description="Lower third title",
                tags=("lower", "title"),
            ),
        )

        # Verify counts
        self.assertEqual(len(registry.list_all()), 4)
        self.assertEqual(len(registry.filter_by_category("video")), 1)
        self.assertEqual(len(registry.filter_by_category("audio")), 1)
        self.assertEqual(len(registry.filter_by_category("transition")), 1)
        self.assertEqual(len(registry.filter_by_category("text")), 1)

        # Filter by tag "color"
        color_effects = registry.filter_by_tag("color")
        self.assertEqual(len(color_effects), 1)
        self.assertEqual(color_effects[0].name, "exposure")

        # Filter by tag "wipe"
        wipe_effects = registry.filter_by_tag("wipe")
        self.assertEqual(len(wipe_effects), 1)
        self.assertEqual(wipe_effects[0].name, "wipe")

        # Validate all
        results = registry.validate_all()
        self.assertEqual(sum(1 for r in results.values() if r is None), 4)

        # Contains / getitem
        self.assertIn("exposure", registry)
        reg = registry["exposure"]
        self.assertEqual(reg.name, "exposure")

    def test_tag_matches_partial(self):
        """matches_tag should be exact match against tags tuple."""
        md = EffectMetadata(name="mod", category="video", tags=("fade", "audio"))
        self.assertTrue(md.matches_tag("fade"))
        self.assertTrue(md.matches_tag("audio"))
        self.assertFalse(md.matches_tag("Fade"))  # case-sensitive
        self.assertFalse(md.matches_tag("fades"))  # not in tuple


# ------------------------------------------------------------------
# Boilerplate
# ------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()