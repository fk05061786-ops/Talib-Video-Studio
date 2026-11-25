"""Qt-free plugin/effect registry for Talib Video Studio.

Provides a centralized registry for registering and validating video/audio/transition
and text effect modules. All operations are Qt-free and head-testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class EffectMetadata:
    """Metadata describing a registered effect module."""

    name: str
    category: str  # "video", "audio", "transition", "text"
    version: str = "0.1.0"
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    author: str = ""
    required_binaries: tuple[str, ...] = field(default_factory=tuple)
    min_fps: float = 0.0
    max_fps: float | None = None
    supports_trim: bool = True
    supports_speed: bool = True

    def matches_tag(self, tag: str) -> bool:
        """Return True if this module carries *tag*."""
        return tag in self.tags


@dataclass
class RegisteredEffect:
    """A fully registered effect module with its class and metadata."""

    name: str
    cls: Type[Any]
    metadata: EffectMetadata


class EffectRegistry:
    """Qt-free plugin registry for NLE effect modules.

    Register video, audio, transition, and text effect modules and then
    query/filter/validate them without any Qt dependency.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, RegisteredEffect] = {}
        self._by_category: Dict[str, List[RegisteredEffect]] = {}
        self._by_tag: Dict[str, List[RegisteredEffect]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        cls: Type[Any],
        metadata: EffectMetadata,
    ) -> None:
        """Register an effect module.

        Parameters
        ----------
        name:
            Unique name within the registry.
        cls:
            The class implementing the effect module.
        metadata:
            :class:`EffectMetadata` describing the module.
        """
        if name in self._modules:
            raise ValueError(f"Effect '{name}' is already registered.")
        registered = RegisteredEffect(name=name, cls=cls, metadata=metadata)
        self._modules[name] = registered

        # Index by category
        cat = metadata.category
        self._by_category.setdefault(cat, []).append(registered)

        # Index by tags
        for tag in metadata.tags:
            self._by_tag.setdefault(tag, []).append(registered)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def has(self, name: str) -> bool:
        """Return True if an effect named *name* is registered."""
        return name in self._modules

    def get(self, name: str) -> RegisteredEffect:
        """Return the RegisteredEffect for *name*, or raise KeyError."""
        if name not in self._modules:
            raise KeyError(f"Effect '{name}' is not registered.")
        return self._modules[name]

    def get_by_category(self, category: str) -> List[RegisteredEffect]:
        """Return all registered effects in *category*."""
        return list(self._by_category.get(category, []))

    def get_by_tag(self, tag: str) -> List[RegisteredEffect]:
        """Return all registered effects that carry *tag*."""
        return list(self._by_tag.get(tag, []))

    def list_all(self) -> List[RegisteredEffect]:
        """Return a copy of all registered RegisteredEffect objects."""
        return list(self._modules.values())

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_module(self, name: str) -> Optional[str]:
        """Validate a registered module and return ``None`` on success.

        Returns a human-readable error message if the module fails validation,
        or ``None`` when the module is valid.
        """
        try:
            reg = self.get(name)
        except KeyError:
            return f"Effect '{name}' is not registered."

        md = reg.metadata
        # Any callable class is considered valid at the registry level.
        if not callable(getattr(reg.cls, "__init__", None)):
            return f"Effect '{name}' class has no callable __init__."

        return None

    def validate_all(self) -> Dict[str, Optional[str]]:
        """Validate all registered modules.

        Returns a dict mapping effect name to ``None`` (valid) or an error string.
        """
        results: Dict[str, Optional[str]] = {}
        for name in self._modules:
            results[name] = self.validate_module(name)
        return results

    # ------------------------------------------------------------------
    # Filtering / introspection
    # ------------------------------------------------------------------

    def filter_by_category(self, category: str) -> List[RegisteredEffect]:
        """Return registered effects whose metadata.category matches *category*."""
        return self.get_by_category(category)

    def filter_by_tag(self, tag: str) -> List[RegisteredEffect]:
        """Return registered effects whose metadata.tags contains *tag*."""
        return self.get_by_tag(tag)

    def filter_by_categories(self, *categories: str) -> List[RegisteredEffect]:
        """Return registered effects whose category is one of *categories*."""
        result: List[RegisteredEffect] = []
        seen: set[str] = set()
        for cat in categories:
            for reg in self._by_category.get(cat, []):
                if reg.name not in seen:
                    seen.add(reg.name)
                    result.append(reg)
        return result

    def filter_by_tags(self, *tags: str) -> List[RegisteredEffect]:
        """Return registered effects that carry *all* of the given tags."""
        if not tags:
            return self.list_all()
        result: List[RegisteredEffect] = []
        seen: set[str] = set()
        for tag in tags:
            for reg in self._by_tag.get(tag, []):
                if reg.name not in seen:
                    seen.add(reg.name)
                    result.append(reg)
        # Further filter: keep only modules carrying every requested tag
        if len(tags) <= 1:
            return result
        filtered: List[RegisteredEffect] = []
        for reg in result:
            md = reg.metadata
            if all(tag in md.tags for tag in tags):
                filtered.append(reg)
        return filtered

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def __getitem__(self, name: str) -> RegisteredEffect:
        return self.get(name)


# ------------------------------------------------------------------
# Convenience: auto-discover modules from a package directory
# ------------------------------------------------------------------

def _module_matches_filename(name: str, filename: str) -> bool:
    """Return True if *name* corresponds to the given *filename* (stem only)."""
    return name.replace("_", "").replace("-", "") == filename.replace(".py", "").replace("-", "").replace("_", "")


def discover_effects(package_dir: str) -> Dict[str, RegisteredEffect]:
    """Discover effect modules under *package_dir*.

    Walks *package_dir* for ``*.py`` files (excluding ``__init__.py``) and,
    for each file whose stem matches a registered effect name, attempts to
    import the module and register any ``EffectRegistry`` subclass instances
    it exposes via a ``get_registry()`` function.

    This is a helper for projects that spread effect implementations across
    many files; the core registry itself is agnostic about discovery.

    Returns a dict mapping effect name to RegisteredEffect.
    """
    import importlib.util
    import os
    import sys

    results: Dict[str, RegisteredEffect] = {}
    seen: set[str] = set()

    if not os.path.isdir(package_dir):
        return results

    for dirpath, _dirnames, filenames in os.walk(package_dir):
        for filename in sorted(filenames):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            filepath = os.path.join(dirpath, filename)
            stem = filename[:-3]  # strip .py

            # Allow the file to be imported relative to package_dir
            rel = os.path.relpath(filepath, package_dir)
            parts = rel.replace(os.sep, ".")[:-3]  # drop .py

            # Basic name cleanup
            mod_name = stem

            if mod_name in seen:
                continue
            seen.add(mod_name)

            try:
                spec = importlib.util.spec_from_file_location(
                    mod_name, filepath, submodule_search_locations=[]
                )
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)  # type: ignore[union-attr]

                # Look for a get_registry() function that returns RegisteredEffect list
                if hasattr(mod, "get_registry"):
                    registry_or_list = mod.get_registry()
                    if isinstance(registry_or_list, list):
                        for reg in registry_or_list:
                            if isinstance(reg, RegisteredEffect):
                                name = reg.name
                                if name not in results:
                                    results[name] = reg
                            elif isinstance(reg, dict) and "name" in reg:
                                # backwards-compat: accept dict-like entries
                                name = reg["name"]
                                if name not in results:
                                    # Store a minimal RegisteredEffect
                                    results[name] = RegisteredEffect(
                                        name=name,
                                        cls=object,
                                        metadata=EffectMetadata(
                                            name=name,
                                            category=reg.get("category", "unknown"),
                                            description=reg.get("description", ""),
                                            tags=tuple(reg.get("tags", [])),
                                        ),
                                    )
                    elif callable(registry_or_list):
                        # Assume it's an EffectRegistry instance
                        for name_, reg in registry_or_list._modules.items():
                            if name_ not in results:
                                results[name_] = reg
            except Exception as exc:  # pragma: no cover
                logger.debug("Skipping effect module %s: %s", filepath, exc)
                pass

    return results