"""Proxy media paths, state and FFmpeg generation helpers (Qt-free)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class ProxySettings:
    """Proxy editing configuration."""

    enabled: bool = False
    scale: float = 0.5
    resolution: str = "960x540"
    folder: str = "proxies"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "scale": float(self.scale),
            "resolution": self.resolution,
            "folder": self.folder,
        }


def normalize_proxy(data: Any = None) -> ProxySettings:
    """Build clamped :class:`ProxySettings` from a dict or settings object."""
    base = ProxySettings()
    if data is None:
        return base
    if isinstance(data, ProxySettings):
        values = data.to_dict()
    elif isinstance(data, dict):
        values = data
    else:
        values = {
            "enabled": getattr(data, "enabled", False),
            "scale": getattr(data, "scale", 0.5),
            "resolution": getattr(data, "resolution", "960x540"),
            "folder": getattr(data, "folder", "proxies"),
        }
    try:
        scale = float(values.get("scale", 0.5))
    except (TypeError, ValueError):
        scale = 0.5
    return ProxySettings(
        enabled=bool(values.get("enabled", False)),
        scale=max(0.1, min(1.0, scale)),
        resolution=str(values.get("resolution", "960x540") or "960x540"),
        folder=str(values.get("folder", "proxies") or "proxies"),
    )


def proxy_path_for(
    source: str | Path, folder: str | Path = "proxies", suffix: str = "_proxy.mp4"
) -> Path:
    """Return the proxy path for *source*, keeping its basename."""
    source_path = Path(source)
    directory = Path(folder)
    if not directory.is_absolute():
        directory = source_path.parent / directory
    return directory / f"{source_path.stem}{suffix}"


def build_proxy_command(
    source: str | Path,
    output: str | Path,
    resolution: str = "960x540",
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Build an FFmpeg command that creates a lightweight H.264 proxy."""
    try:
        width, height = (int(part) for part in resolution.lower().split("x"))
        if width <= 0 or height <= 0:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError(f"Invalid proxy resolution '{resolution}'")
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(source),
        "-vf",
        f"scale={width}:{height}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        str(output),
    ]


def generate_proxy(
    source: str | Path,
    output: str | Path,
    resolution: str = "960x540",
    ffmpeg_bin: str = "ffmpeg",
) -> Tuple[bool, str]:
    """Generate a proxy file, returning ``(success, message)``."""
    source_path = Path(source)
    if not source_path.is_file():
        return False, f"Source media not found: {source_path}"
    try:
        command = build_proxy_command(source_path, output, resolution, ffmpeg_bin)
    except ValueError as exc:
        return False, str(exc)
    output_path = Path(output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Could not create proxy directory: {exc}"
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except (OSError, FileNotFoundError):
        return False, f"FFmpeg binary not found: '{ffmpeg_bin}'"
    if result.returncode != 0:
        return False, result.stderr.strip() or "FFmpeg reported an error while creating proxy."
    return True, str(output_path)


class ProxyManager:
    """Resolve source media to proxies and generate them on demand."""

    def __init__(
        self, settings: Any = None, ffmpeg_bin: str = "ffmpeg"
    ) -> None:
        self.settings = normalize_proxy(settings)
        self.ffmpeg_bin = ffmpeg_bin

    def set_settings(self, settings: Any) -> None:
        self.settings = normalize_proxy(settings)

    def path_for(self, source: str | Path) -> Path:
        return proxy_path_for(source, self.settings.folder)

    def resolve(self, source: str | Path) -> Path:
        """Return the proxy when enabled and present, otherwise the source."""
        candidate = self.path_for(source)
        if self.settings.enabled and candidate.is_file():
            return candidate
        return Path(source)

    def ensure(
        self, source: str | Path, resolution: str | None = None
    ) -> Tuple[bool, str]:
        """Ensure a proxy exists; generate it when missing."""
        target = self.path_for(source)
        if target.is_file():
            return True, str(target)
        return generate_proxy(
            source,
            target,
            resolution or self.settings.resolution,
            self.ffmpeg_bin,
        )
