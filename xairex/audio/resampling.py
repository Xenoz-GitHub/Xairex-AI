"""Streaming resampling: device rate -> 16 kHz mono int16.

The microphone module hands out frames at the device's native rate (16 kHz is
probed first, but many devices only support 44.1/48 kHz). Wake-word scoring,
endpointing and Whisper all run in the 16 kHz domain, so frames are converted
with **soxr** (LGPL-2.1-or-later, pinned 1.1.0; wheel verified working on this
machine, hence soxr rather than ``scipy.signal.resample_poly``).

``StreamResampler`` keeps filter state across calls, so chunk boundaries do not
introduce clicks and the sample rate stays exact over long captures. A small
filter delay (a few ms) is inherent to streaming resamplers and harmless for
this frame-based pipeline.
"""

from __future__ import annotations

import numpy as np
import soxr

#: The processing domain used by wake word, recorder and Whisper.
TARGET_RATE = 16000


class StreamResampler:
    """Continuous int16 mono resampler for one capture stream."""

    def __init__(self, in_rate: int, out_rate: int = TARGET_RATE, *, quality: str = "HQ") -> None:
        if in_rate <= 0 or out_rate <= 0:
            raise ValueError(f"Sample rates must be positive (got in_rate={in_rate}, out_rate={out_rate}).")
        self._in_rate = int(in_rate)
        self._out_rate = int(out_rate)
        self._passthrough = self._in_rate == self._out_rate
        self._stream = (
            None
            if self._passthrough
            else soxr.ResampleStream(self._in_rate, self._out_rate, 1, dtype="int16", quality=quality)
        )

    @property
    def in_rate(self) -> int:
        return self._in_rate

    @property
    def out_rate(self) -> int:
        return self._out_rate

    @property
    def passthrough(self) -> bool:
        """True when in_rate == out_rate (no filtering is applied)."""
        return self._passthrough

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Resample one frame; returns 1-D int16 (possibly empty, never None)."""
        data = np.asarray(frame, dtype=np.int16).reshape(-1)
        if self._passthrough or data.size == 0:
            return data
        out = self._stream.resample_chunk(data)
        if out is None:  # filter still filling; nothing available yet
            return np.empty(0, dtype=np.int16)
        return np.asarray(out, dtype=np.int16).reshape(-1)

    def reset(self) -> None:
        """Drop filter state (start a fresh stream, e.g. after a device switch)."""
        if self._stream is not None:
            self._stream.clear()


def resample_int16(data: np.ndarray, in_rate: int, out_rate: int = TARGET_RATE) -> np.ndarray:
    """One-shot resample of a complete int16 buffer."""
    if in_rate <= 0 or out_rate <= 0:
        raise ValueError(f"Sample rates must be positive (got in_rate={in_rate}, out_rate={out_rate}).")
    samples = np.asarray(data, dtype=np.int16).reshape(-1)
    if in_rate == out_rate or samples.size == 0:
        return samples
    return np.asarray(soxr.resample(samples, in_rate, out_rate), dtype=np.int16).reshape(-1)
