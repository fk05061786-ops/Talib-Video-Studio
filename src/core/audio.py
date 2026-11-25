"""Audio waveform peak helpers (no Qt dependency).

Converts raw PCM samples into normalized buckets suitable for drawing, and
optionally extracts them with FFmpeg. Pure functions are unit-testable without
media files or a display.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def pcm_to_peaks(
    data: bytes,
    bucket_count: int = 160,
    sample_width: int = 2,
    channels: int = 1,
    max_samples_per_bucket: int = 64,
) -> List[float]:
    """Return normalized ``0..1`` peaks from little-endian PCM *data*."""
    if bucket_count <= 0 or sample_width <= 0 or channels <= 0:
        return []
    frame_bytes = sample_width * channels
    frame_count = len(data) // frame_bytes
    if frame_count == 0:
        return []

    bucket_size = max(1, frame_count // bucket_count)
    stride = max(1, bucket_size // max(1, max_samples_per_bucket))
    peaks: List[float] = []
    for bucket in range(bucket_count):
        start = bucket * bucket_size
        end = min(frame_count, start + bucket_size)
        if start >= end:
            break
        peak = 0
        for frame in range(start, end, stride):
            offset = frame * frame_bytes
            sample = int.from_bytes(
                data[offset : offset + sample_width], "little", signed=True
            )
            peak = max(peak, abs(sample))
        peaks.append(float(peak))

    ceiling = max(peaks)
    if ceiling <= 0:
        return [0.0] * len(peaks)
    return [min(1.0, peak / ceiling) for peak in peaks]


def resample_peaks(peaks: List[float], bucket_count: int) -> List[float]:
    """Resample existing peaks into *bucket_count* buckets using bucket maxima."""
    if bucket_count <= 0 or not peaks:
        return []
    result: List[float] = []
    for index in range(bucket_count):
        start = index * len(peaks) // bucket_count
        end = max(start + 1, (index + 1) * len(peaks) // bucket_count)
        result.append(max(peaks[start:end]))
    return result


def peaks_to_bars(
    peaks: List[float], width: float, height: float
) -> List[Tuple[float, float, float]]:
    """Convert normalized peaks into ``(x, top, bottom)`` drawing bars."""
    if not peaks or width <= 0 or height <= 0:
        return []
    bar_width = width / len(peaks)
    mid = height / 2.0
    bars = []
    for index, peak in enumerate(peaks):
        extent = max(1.0, min(1.0, peak) * mid * 0.9)
        x = index * bar_width
        bars.append((x, mid - extent, mid + extent))
    return bars


def extract_waveform_peaks(
    path: str | Path,
    bucket_count: int = 160,
    start_sec: Optional[float] = None,
    duration_sec: Optional[float] = None,
    ffmpeg_bin: str = "ffmpeg",
) -> List[float]:
    """Decode mono PCM with FFmpeg and return normalized waveform peaks."""
    cmd = [ffmpeg_bin]
    if start_sec is not None:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
    cmd.extend(["-i", str(path)])
    if duration_sec is not None:
        cmd.extend(["-t", f"{duration_sec:.3f}"])
    cmd.extend(["-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"])
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except (OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    return pcm_to_peaks(result.stdout, bucket_count=bucket_count)
