"""Speaker playback with interruption support (spec sections 3 and 6).

One short-lived ``sounddevice.OutputStream`` per utterance. The PCM bytes are
decoded to an int16 numpy view once; the audio callback only copies samples
from that view — no inference, no logging, no locks beyond a single position
counter. ``Playback.stop()`` is safe to call from any thread (the 'stop'
command and Ctrl+C use it).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np

from xairex.speech.synthesizer import Pcm

logger = logging.getLogger("xairex.playback")


class PlaybackError(RuntimeError):
    """Raised when the audio output device cannot be used."""


@dataclass(frozen=True)
class OutputDevice:
    """One playable output device as reported by PortAudio."""

    index: int
    name: str
    max_output_channels: int
    default_samplerate: float


def list_output_devices(sd: object | None = None) -> list[OutputDevice]:
    """All devices that can play audio, in PortAudio order (G4 device picker).

    Enumeration only — no stream is opened. Raises :class:`PlaybackError`
    when the ``sounddevice`` package (PortAudio) is unavailable.
    """
    module = sd
    if module is None:
        try:
            import sounddevice
        except ImportError as exc:
            raise PlaybackError("The 'sounddevice' package is not installed. Run scripts\\install.ps1.") from exc
        module = sounddevice
    try:
        raw = module.query_devices()  # type: ignore[attr-defined]
    except Exception as exc:
        raise PlaybackError(f"Could not list audio devices: {exc}") from exc

    devices: list[OutputDevice] = []
    for entry in raw or []:
        channels = int(entry.get("max_output_channels", 0) or 0)
        if channels <= 0:
            continue
        devices.append(
            OutputDevice(
                index=int(entry.get("index", -1)),
                name=str(entry.get("name", "?")),
                max_output_channels=channels,
                default_samplerate=float(entry.get("default_samplerate", 0.0) or 0.0),
            )
        )
    return devices


def _stream_is_active(stream: object) -> bool:
    """True while the output stream is running (guards against callback deaths)."""
    active = getattr(stream, "active", True)
    try:
        return bool(active() if callable(active) else active)
    except Exception:  # noqa: BLE001 - device quirk: assume it is alive
        return True


class Playback:
    """Sequential PCM playback through one output stream at a time."""

    def __init__(self, output_device: int | None = None, sd: object | None = None) -> None:
        self._device = output_device
        self._sd = sd
        self._interrupt = threading.Event()
        self._active_stream: object | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: object) -> Playback:
        """Build from :class:`xairex.config.Settings`."""
        return cls(output_device=settings.audio.output_device)

    def _get_sd(self) -> object:
        if self._sd is None:
            try:
                import sounddevice
            except ImportError as exc:
                raise PlaybackError("The 'sounddevice' package is not installed. Run scripts\\install.ps1.") from exc
            self._sd = sounddevice
        return self._sd

    def play(self, pcm: Pcm, cancel_event: threading.Event | None = None) -> float:
        """Play *pcm* and block until done, stopped or cancelled.

        Returns the approximate number of seconds that were played.
        """
        if not pcm.data:
            return 0.0
        if pcm.sample_width != 2:
            raise PlaybackError(f"Unsupported sample width: {pcm.sample_width * 8} bit (expected 16-bit PCM).")

        sd = self._get_sd()
        self._interrupt.clear()

        data = pcm.data
        channels = pcm.channels
        frame_width = channels * pcm.sample_width
        total_frames = len(data) // frame_width
        if total_frames <= 0:
            return 0.0
        # Decode the whole utterance to one int16 view. The callback must copy
        # *samples*: assigning raw bytes into the int16 buffer makes numpy try
        # to parse them as text and raise inside the audio callback (observed
        # 2026-10-16; fixed here + regression-tested in tests/test_playback.py).
        samples = np.frombuffer(data[: total_frames * frame_width], dtype=np.int16)

        state = {"position": 0}
        done = threading.Event()

        def _callback(outdata, frames, time_info, status) -> None:  # real-time: keep it trivial
            position = state["position"]
            playable = min(frames, max(total_frames - position, 0))
            if playable > 0:
                block = samples[position * channels : (position + playable) * channels]
                outdata[:playable] = block.reshape(playable, channels)
                state["position"] = position + playable
            if playable < frames:
                # Final (partial) block: fill the tail with silence and finish.
                outdata[playable:] = 0
                done.set()
                stop_exception = getattr(sd, "CallbackStop", None)
                if stop_exception is not None:
                    raise stop_exception

        try:
            stream = sd.OutputStream(
                samplerate=pcm.sample_rate,
                channels=pcm.channels,
                dtype="int16",
                device=self._device,
                callback=_callback,
            )
        except Exception as exc:
            raise PlaybackError(f"Could not open the audio output device: {exc}") from exc

        with self._lock:
            self._active_stream = stream
        try:
            stream.start()
            while not done.is_set():
                if self._interrupt.is_set() or (cancel_event is not None and cancel_event.is_set()):
                    break
                if not _stream_is_active(stream):
                    break  # the callback died or the device stopped on its own
                done.wait(0.05)
        finally:
            with self._lock:
                self._active_stream = None
            try:
                if done.is_set():
                    stream.stop()
                else:
                    stream.abort()  # interrupt/cancel: cut off immediately
            except Exception:  # pragma: no cover - device teardown is best-effort
                logger.debug("Ignoring error while stopping the output stream", exc_info=True)
            try:
                stream.close()
            except Exception:  # pragma: no cover
                logger.debug("Ignoring error while closing the output stream", exc_info=True)

        played_frames = min(state["position"], total_frames)
        if self._interrupt.is_set() or (cancel_event is not None and cancel_event.is_set()):
            logger.debug("Playback interrupted after %d frames", played_frames)
        return played_frames / pcm.sample_rate

    def stop(self) -> None:
        """Interrupt the current playback immediately (safe from any thread)."""
        self._interrupt.set()
        with self._lock:
            stream = self._active_stream
        if stream is not None:
            try:
                stream.abort()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                logger.debug("Ignoring error while aborting the output stream", exc_info=True)

    def close(self) -> None:
        """Release any active playback resources."""
        self.stop()
