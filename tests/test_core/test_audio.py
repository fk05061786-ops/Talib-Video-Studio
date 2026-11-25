"""Headless tests for audio waveform peak helpers."""

import struct
import unittest

from src.core.audio import peaks_to_bars, pcm_to_peaks, resample_peaks


def pcm(*values: int) -> bytes:
    return b"".join(struct.pack("<h", value) for value in values)


class TestAudioPeaks(unittest.TestCase):
    def test_pcm_peaks_are_bucketed_and_normalized(self):
        peaks = pcm_to_peaks(pcm(0, 10, 0, 20, 0, 40, 0, 80), bucket_count=4)
        self.assertEqual(peaks, [0.125, 0.25, 0.5, 1.0])

    def test_silence(self):
        self.assertEqual(pcm_to_peaks(pcm(0, 0, 0, 0), 2), [0.0, 0.0])

    def test_empty_and_invalid(self):
        self.assertEqual(pcm_to_peaks(b"", 4), [])
        self.assertEqual(pcm_to_peaks(pcm(1, 2), 0), [])

    def test_resample_peaks(self):
        self.assertEqual(resample_peaks([1.0, 0.0, 0.5, 0.25], 2), [1.0, 0.5])
        self.assertEqual(resample_peaks([], 4), [])

    def test_peaks_to_bars(self):
        bars = peaks_to_bars([0.0, 1.0], 100, 20)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0], (0.0, 10.0 - 1.0, 10.0 + 1.0))
        self.assertEqual(bars[1][0], 50.0)
        self.assertEqual(peaks_to_bars([], 100, 20), [])


if __name__ == "__main__":
    unittest.main()
