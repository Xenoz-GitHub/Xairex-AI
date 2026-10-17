"""Endpointing: energy/RMS silence endpointer over 16 kHz mono int16 frames.

The recorder turns a stream of 16 kHz frames (microphone -> resampling output)
into utterances:

  * capture starts after ``speech_start_frames`` consecutive frames whose RMS
    crosses ``speech_threshold_db`` (dBFS) - a single click or pop is not
    enough (measured room-noise tuning: see notes/05-DECISIONS-RISKS.md, D18);
  * ``pre_roll_seconds`` of audio preceding that frame is prepended, so the
    first syllable is not clipped;
  * capture ends after ``silence_end_seconds`` of trailing silence;
  * bursts with less than ``min_speech_seconds`` of voiced audio are treated
    as noise and discarded (``feed``/``flush`` return ``None``);
  * ``max_record_seconds`` is a hard cap (long monologues are truncated).

Only the live utterance buffer is retained; it is released as soon as an
utterance is returned or dropped. Frames may be any length; empty frames are
ignored.
"""

from __future__ import annotations

import math

import numpy as np

from xairex.audio.resampling import TARGET_RATE
from xairex.config import Settings


class Recorder:
    """Push frames in with :meth:`feed`; get complete utterances (int16) out."""

    def __init__(
        self,
        sample_rate: int = TARGET_RATE,
        *,
        min_speech_seconds: float = 0.4,
        silence_end_seconds: float = 1.2,
        pre_roll_seconds: float = 0.3,
        max_record_seconds: float = 15.0,
        threshold_db: float = -40.0,
        speech_start_frames: int = 2,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive (got {sample_rate}).")
        if min_speech_seconds <= 0 or silence_end_seconds <= 0 or max_record_seconds <= 0:
            raise ValueError("min_speech_seconds, silence_end_seconds and max_record_seconds must be positive.")
        if pre_roll_seconds < 0:
            raise ValueError("pre_roll_seconds must be zero or positive.")
        if speech_start_frames < 1:
            raise ValueError("speech_start_frames must be at least 1.")

        self._rate = int(sample_rate)
        self.min_speech_samples = max(1, round(min_speech_seconds * self._rate))
        self.silence_end_samples = max(1, round(silence_end_seconds * self._rate))
        self.pre_roll_samples = round(pre_roll_seconds * self._rate)
        self.max_record_samples = max(1, round(max_record_seconds * self._rate))
        self.threshold_db = float(threshold_db)
        self.speech_start_frames = int(speech_start_frames)

        self._buffer: list[np.ndarray] = []
        self._preroll: list[np.ndarray] = []
        self._preroll_samples = 0
        self._total_samples = 0
        self._voiced_samples = 0
        self._silent_run = 0
        self._voiced_run_frames = 0
        self._voiced_run_samples = 0
        self._recording = False

    @classmethod
    def from_settings(cls, settings: Settings, sample_rate: int = TARGET_RATE) -> Recorder:
        """Build from config. ``sample_rate`` is the rate of the frames you feed
        (the 16 kHz processing domain), not the capture probe rate."""
        audio = settings.audio
        return cls(
            sample_rate,
            min_speech_seconds=audio.min_speech_seconds,
            silence_end_seconds=audio.silence_end_seconds,
            pre_roll_seconds=audio.pre_roll_seconds,
            max_record_seconds=audio.max_record_seconds,
            threshold_db=audio.speech_threshold_db,
            speech_start_frames=audio.speech_start_frames,
        )

    # ------------------------------------------------------------- properties

    @property
    def sample_rate(self) -> int:
        return self._rate

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------- feed

    def feed(self, frame: np.ndarray) -> np.ndarray | None:
        """Add one frame; returns a complete utterance (int16, 1-D) or ``None``."""
        data = np.asarray(frame, dtype=np.int16).reshape(-1)
        if data.size == 0:
            return None

        if not self._recording:
            self._push_preroll(data)
            if self._is_voiced(data):
                self._voiced_run_frames += 1
                self._voiced_run_samples += len(data)
                if self._voiced_run_frames >= self.speech_start_frames:
                    self._start_recording()
            else:
                self._voiced_run_frames = 0
                self._voiced_run_samples = 0
            return None

        self._buffer.append(data)
        self._total_samples += len(data)
        if self._is_voiced(data):
            self._voiced_samples += len(data)
            self._silent_run = 0
        else:
            self._silent_run += len(data)

        if self._silent_run >= self.silence_end_samples or self._total_samples >= self.max_record_samples:
            return self._finish()
        return None

    def flush(self) -> np.ndarray | None:
        """End any capture in progress now (shutdown path). May return ``None``."""
        if not self._recording:
            return None
        return self._finish()

    def cancel(self) -> None:
        """Abort any capture in progress; buffered audio is dropped."""
        self._reset()

    # ---------------------------------------------------------------- internals

    def _push_preroll(self, data: np.ndarray) -> None:
        self._preroll.append(data)
        self._preroll_samples += len(data)
        while self._preroll and self._preroll_samples > self.pre_roll_samples:
            dropped = self._preroll.pop(0)
            self._preroll_samples -= len(dropped)

    def _start_recording(self) -> None:
        self._recording = True
        self._buffer = list(self._preroll)  # includes the voiced run that triggered
        self._total_samples = self._preroll_samples
        self._voiced_samples = min(self._voiced_run_samples, self._total_samples)
        self._voiced_run_frames = 0
        self._voiced_run_samples = 0
        self._silent_run = 0

    def _finish(self) -> np.ndarray | None:
        buffer = self._buffer
        voiced = self._voiced_samples
        self._reset()  # release the live buffers before doing anything else
        if voiced < self.min_speech_samples or not buffer:
            return None
        utterance = np.concatenate(buffer)
        if len(utterance) > self.max_record_samples:
            utterance = utterance[: self.max_record_samples]
        return utterance

    def _reset(self) -> None:
        self._buffer = []
        self._preroll = []
        self._preroll_samples = 0
        self._total_samples = 0
        self._voiced_samples = 0
        self._silent_run = 0
        self._voiced_run_frames = 0
        self._voiced_run_samples = 0
        self._recording = False

    def _is_voiced(self, data: np.ndarray) -> bool:
        samples = data.astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms <= 0.0:
            return False
        return 20.0 * math.log10(rms / 32768.0) >= self.threshold_db
