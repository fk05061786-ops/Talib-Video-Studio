"""Standard built-in effects registration for Talib Video Studio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.core.effects_registry import EffectMetadata, EffectRegistry


@dataclass
class BuiltinVideoEffect:
    name: str
    params: Dict[str, Any]


@dataclass
class BuiltinAudioEffect:
    name: str
    params: Dict[str, Any]


@dataclass
class BuiltinTransitionEffect:
    name: str
    params: Dict[str, Any]


@dataclass
class BuiltinTextEffect:
    name: str
    params: Dict[str, Any]


def create_default_registry() -> EffectRegistry:
    """Create and populate a default EffectRegistry with built-in effects."""
    registry = EffectRegistry()

    # Video Effects
    registry.register(
        "brightness",
        BuiltinVideoEffect,
        EffectMetadata(
            name="brightness",
            category="video",
            description="Adjusts image brightness",
            tags=("color", "video"),
        ),
    )
    registry.register(
        "contrast",
        BuiltinVideoEffect,
        EffectMetadata(
            name="contrast",
            category="video",
            description="Adjusts image contrast",
            tags=("color", "video"),
        ),
    )

    # Audio Effects
    registry.register(
        "gain",
        BuiltinAudioEffect,
        EffectMetadata(
            name="gain",
            category="audio",
            description="Adjusts audio volume/gain",
            tags=("volume", "audio"),
        ),
    )

    # Transitions
    registry.register(
        "crossfade",
        BuiltinTransitionEffect,
        EffectMetadata(
            name="crossfade",
            category="transition",
            description="Standard video crossfade transition",
            tags=("fade", "transition"),
        ),
    )

    # Text
    registry.register(
        "title",
        BuiltinTextEffect,
        EffectMetadata(
            name="title",
            category="text",
            description="Centered video title overlay",
            tags=("title", "text"),
        ),
    )

    return registry
