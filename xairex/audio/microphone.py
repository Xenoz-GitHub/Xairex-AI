"""Microphone capture: device enumeration, rate probing, bounded frame queue.

Design rules (notes/02-ARCHITECTURE.md §4):
  - the sounddevice callback does the absolute minimum: copy the frame and push
    it onto a bounded queue (drop-oldest + overflow counter). It never blocks,
    never logs and never raises.
  - all heavy work (resampling, wake-word scoring, endpointing) happens on the
    engine thread, which consumes frames via :meth:`Microphone.read_frame`.

The stream opens at the best supported device rate; frames are handed out
unchanged in the device rate. ``audio/resampling.py`` (T2.2) converts them to
the 16 kHz processing domain.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass
from typing import Any, Self

import numpy as np

from xairex.config import Settings

logger = logging.getLogger(__name__)

#: Rates to probe when the preferred rate is not supported (order matters).
FALLBACK_RATES: tuple[int, ...] = (48000, 44100)

#: PortAudio error substrings (lowercased) -> actionable hint for the user.
_PORT_AUDIO_HINTS: tuple[tuple[str, str], ...] = (
    ("error querying device", "the device index is invalid — list the devices and pick an existing index"),
    ("invalid number of channels", "the device cannot capture mono — pick another input device"),
    ("device unavailable", "the device is disconnected, disabled or in exclusive use by another app"),
    ("unanticipated host error", "the device is busy (often WASAPI exclusive mode) — close other apps using it"),
    ("insufficient memory", "the system is low on resources"),
)


class MicrophoneError(RuntimeError):
    """Raised when an input device cannot be found, probed or opened."""


@dataclass(frozen=True)
class InputDevice:
    """One capturable input device as reported by PortAudio."""

    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


def _sd_module(sd: Any | None) -> Any:
    if sd is not None:
        return sd
    import sounddevice  # lazy: unit tests never need PortAudio installed

    return sounddevice


def _explain(exc: Exception) -> str:
    """Append an actionable hint for common PortAudio failures."""
    text = str(exc)
    lowered = text.lower()
    for needle, hint in _PORT_AUDIO_HINTS:
        if needle in lowered:
            return f"{text} — {hint}"
    return text


def list_input_devices(sd: Any | None = None) -> list[InputDevice]:
    """All devices that can capture audio, in PortAudio order."""
    module = _sd_module(sd)
    try:
        raw = module.query_devices()
    except Exception as exc:
        raise MicrophoneError(f"Could not list audio devices: {_explain(exc)}") from exc

    devices: list[InputDevice] = []
    for entry in raw or []:
        channels = int(entry.get("max_input_channels", 0) or 0)
        if channels <= 0:
            continue
        devices.append(
            InputDevice(
                index=int(entry.get("index", -1)),
                name=str(entry.get("name", "?")),
                max_input_channels=channels,
                default_samplerate=float(entry.get("default_samplerate", 0.0) or 0.0),
            )
        )
    return devices


class Microphone:
    """Mono int16 input stream feeding a bounded drop-oldest frame queue."""

    def __init__(
        self,
        *,
        device_index: int | None = None,
        sample_rate: int = 16000,
        frame_ms: int = 80,
        queue_max_frames: int = 100,
        sd: Any | None = None,
    ) -> None:
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if queue_max_frames < 1:
            raise ValueError("queue_max_frames must be at least 1")
        self._device_index = device_index
        self._preferred_rate = int(sample_rate)
        self._frame_ms = int(frame_ms)
        self._sd = _sd_module(sd)
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=int(queue_max_frames))
        self._stream: Any | None = None
        self._device_rate: int | None = None
        self._device_name = "(default input)"
        self._frame_samples = 0
        #: Frames dropped because the consumer fell behind (diagnostics only).
        self.overflow_count = 0
        #: Callbacks that carried a PortAudio status flag (xruns etc.).
        self.status_count = 0
        #: Exceptions swallowed inside the callback to protect the stream.
        self.callback_errors = 0

    @classmethod
    def from_settings(cls, settings: Settings, sd: Any | None = None) -> Microphone:
        audio = settings.audio
        return cls(
            device_index=audio.input_device,
            sample_rate=audio.sample_rate,
            frame_ms=audio.frame_ms,
            queue_max_frames=audio.queue_max_frames,
            sd=sd,
        )

    # ------------------------------------------------------------- properties

    @property
    def device_index(self) -> int | None:
        return self._device_index

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device_rate(self) -> int:
        """Actual capture rate chosen at :meth:`open` time."""
        if self._device_rate is None:
            raise MicrophoneError("Microphone is not open.")
        return self._device_rate

    @property
    def frame_samples(self) -> int:
        """Samples per frame at the device rate (0 until opened)."""
        return self._frame_samples

    @property
    def is_open(self) -> bool:
        return self._stream is not None

    # ------------------------------------------------------------ open/close

    def open(self) -> None:
        """Validate the device, probe a working rate and start the stream."""
        if self._stream is not None:
            raise MicrophoneError("Microphone is already open.")

        device = self._device_index
        device_default = 0.0
        if device is None:
            try:
                info = self._sd.query_devices(kind="input")
                device_default = float(info.get("default_samplerate", 0.0) or 0.0)
                name = str(info.get("name", "default"))
                self._device_name = f"{name} (system default)"
            except Exception:  # noqa: BLE001 - probing only; default device survives
                self._device_name = "(system default input)"
        else:
            known = list_input_devices(self._sd)
            by_index = {d.index: d for d in known}
            if device not in by_index:
                available = ", ".join(f"{d.index}: {d.name}" for d in known) or "none"
                raise MicrophoneError(
                    f"Input device {device} does not exist. Available input devices: {available}. "
                    "Fix 'audio.input_device' in config/settings.json."
                )
            self._device_name = by_index[device].name
            device_default = by_index[device].default_samplerate

        chosen: int | None = None
        errors: list[str] = []
        for rate in self._candidate_rates(device_default):
            try:
                self._sd.check_input_settings(device=device, channels=1, dtype="int16", samplerate=rate)
                chosen = rate
                break
            except Exception as exc:  # noqa: BLE001 - collect all probe failures
                errors.append(f"{rate} Hz: {_explain(exc)}")

        if chosen is None:
            detail = "; ".join(errors) or "no candidate rates"
            raise MicrophoneError(
                f"Cannot capture from '{self._device_name}': none of the candidate rates worked "
                f"({detail}). Try another device (config audio.input_device) or close other apps "
                "that use the microphone."
            )

        frame_samples = max(1, round(chosen * self._frame_ms / 1000))
        try:
            self._stream = self._sd.InputStream(
                samplerate=chosen,
                blocksize=frame_samples,
                device=device,
                channels=1,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise MicrophoneError(
                f"Could not open the microphone ('{self._device_name}' @ {chosen} Hz): {_explain(exc)}"
            ) from exc

        self._device_rate = chosen
        self._frame_samples = frame_samples
        logger.info(
            "Microphone open: '%s' @ %d Hz, frame %d ms = %d samples",
            self._device_name,
            chosen,
            self._frame_ms,
            frame_samples,
        )

    def close(self) -> None:
        """Stop and release the stream. Safe to call repeatedly."""
        stream, self._stream = self._stream, None
        if stream is None:
            return
        for action in (getattr(stream, "stop", None), getattr(stream, "close", None)):
            if callable(action):
                try:
                    action()
                except Exception:
                    logger.debug("Ignoring error while releasing the microphone stream", exc_info=True)
        logger.info(
            "Microphone closed (dropped frames: %d, status flags: %d, callback errors: %d)",
            self.overflow_count,
            self.status_count,
            self.callback_errors,
        )

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ frames

    def read_frame(self, timeout: float | None = None) -> np.ndarray | None:
        """Pop the oldest captured frame, or ``None`` when none arrives in time."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> int:
        """Discard queued frames (e.g. stale audio from before push-to-talk).

        Returns the number of frames dropped.
        """
        drained = 0
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return drained
            drained += 1

    def _candidate_rates(self, device_default: float) -> list[int]:
        candidates: list[int] = []
        for rate in (self._preferred_rate, *FALLBACK_RATES):
            if rate and rate not in candidates:
                candidates.append(int(rate))
        if device_default and int(device_default) not in candidates:
            candidates.append(int(device_default))
        return candidates

    def _callback(self, indata: Any, frames: int, time_info: Any, status: Any) -> None:
        """sounddevice callback: copy the frame, enqueue it. Never blocks or raises."""
        try:
            if status:
                self.status_count += 1
            frame = np.array(indata[:, 0], dtype=np.int16, copy=True)
            while True:
                try:
                    self._queue.put_nowait(frame)
                    return
                except queue.Full:
                    try:
                        self._queue.get_nowait()  # drop the oldest frame
                    except queue.Empty:
                        continue  # consumer drained it; retry the put
                    self.overflow_count += 1
        except Exception:  # noqa: BLE001 - raising here would abort the stream
            self.callback_errors += 1
