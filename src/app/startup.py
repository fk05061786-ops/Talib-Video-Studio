"""Qt-free application startup helpers.

Effect registration happens here so it can be tested headlessly. Every optional
step is guarded: a broken built-in set or a bad custom effects folder must never
prevent the application from starting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.effects_registry import EffectRegistry, discover_effects

logger = logging.getLogger(__name__)


def init_effect_registry(
    config: Optional[Dict[str, Any]] = None,
    extra_dir: Optional[str | Path] = None,
) -> EffectRegistry:
    """Build the effect registry from built-ins plus optional custom modules."""
    config = config or {}
    try:
        from src.core.builtin_effects import create_default_registry

        registry = create_default_registry()
        logger.info("Registered %d built-in effects", len(registry.list_all()))
    except Exception:
        logger.exception("Built-in effect registry failed to initialize")
        registry = EffectRegistry()

    directory = extra_dir or config.get("EFFECTS_DIR")
    if directory:
        try:
            discovered = discover_effects(str(directory))
            for name, entry in discovered.items():
                if registry.has(name):
                    continue
                try:
                    registry.register(name, entry.cls, entry.metadata)
                except Exception:
                    logger.exception("Could not register custom effect '%s'", name)
        except Exception:
            logger.exception("Optional effect discovery failed; continuing")

    try:
        invalid = [name for name, error in registry.validate_all().items() if error]
    except Exception:
        logger.exception("Effect validation failed; continuing")
        invalid = []
    if invalid:
        logger.warning("Invalid effects skipped: %s", ", ".join(invalid))
    return registry
