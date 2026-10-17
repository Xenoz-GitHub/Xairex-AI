"""Local speech-to-text with faster-whisper (spec section 5; CPU only).

The Whisper model is loaded once from the project-local model directory that
``scripts\\prepare_models.ps1`` downloaded ahead of time. An explicit directory
path plus ``local_files_only=True`` guarantee the runtime never fetches
anything. The Silero VAD model used by ``vad_filter`` ships inside the
faster-whisper wheel (verified 2026-10-16), so VAD is fully offline too.

Privacy: transcripts reach the log only when ``logging.debug_log_private`` is
enabled; otherwise only timing/size metadata is logged.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from xairex.config import Settings

logger = logging.getLogger("xairex.stt")

#: Extra vocabulary always worth biasing toward (checked against sightings).
_COMMAND_WORDS = (
    "wifi",
    "volume",
    "set the volume",
    "turn the volume",
    "percent",
    "mute",
    "unmute",
    "louder",
    "quieter",
    "pause",
    "resume",
    "stop",
    "next",
    "previous",
)


class SttError(RuntimeError):
    """Raised when the local model is missing or transcription fails."""


def default_hotwords(settings: Settings) -> str:
    """Command vocabulary that biases Whisper toward the words spoken here.

    Known and learned app names and site aliases are pulled from the live
    configuration, so teaching Xairex a new app also teaches the recognizer.
    A user-provided ``stt.hotwords`` string is prepended.
    """
    words: list[str] = []
    user = str(getattr(settings.stt, "hotwords", "") or "").strip()
    if user:
        words.append(user)
    words.append("Xairex")
    try:
        from xairex.tools.applications import known_app_names
        from xairex.tools.websites import site_aliases

        words.extend(sorted(known_app_names(settings)))
        words.extend(sorted(site_aliases(settings)))
    except Exception:
        logger.debug("Could not build the app/site vocabulary for hotwords", exc_info=True)
    words.extend(_COMMAND_WORDS)

    seen: set[str] = set()
    unique: list[str] = []
    for chunk in words:
        key = chunk.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(chunk.strip())
    return ", ".join(unique)


class Transcriber:
    """faster-whisper wrapper pinned to CPU; one model instance, reused."""

    def __init__(
        self,
        model_dir: str | Path,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        beam_size: int = 5,
        language: str = "en",
        vad_filter: bool = True,
        timeout_seconds: float = 180.0,
        debug_log_private: bool = False,
        hotwords: str = "",
        condition_on_previous_text: bool = False,
        model: Any | None = None,
    ) -> None:
        if device != "cpu":
            raise ValueError(f"Transcriber is CPU-only by design (got device={device!r}).")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        self._model_dir = Path(model_dir)
        self._compute_type = compute_type
        self._cpu_threads = int(cpu_threads)
        self._beam_size = int(beam_size)
        self._language = language
        self._vad_filter = bool(vad_filter)
        self._timeout_seconds = float(timeout_seconds)
        self._debug_log_private = bool(debug_log_private)
        self._hotwords = str(hotwords or "").strip()
        self._condition_on_previous_text = bool(condition_on_previous_text)
        self._model = model

    @classmethod
    def from_settings(cls, settings: Settings, model: Any | None = None) -> Transcriber:
        stt = settings.stt
        return cls(
            settings.resolve_path(stt.model_dir),
            device=stt.device,
            compute_type=stt.compute_type,
            cpu_threads=stt.cpu_threads,
            beam_size=stt.beam_size,
            language=stt.language,
            vad_filter=stt.vad_filter,
            timeout_seconds=stt.timeout_seconds,
            debug_log_private=settings.logging.debug_log_private,
            hotwords=default_hotwords(settings),
            condition_on_previous_text=bool(getattr(stt, "condition_on_previous_text", False)),
            model=model,
        )

    # ------------------------------------------------------------------ model

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        """Load the model now (startup warm-up). Never downloads anything."""
        self._ensure_model()

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self._model_dir.is_dir():
            raise SttError(
                f"Whisper model directory '{self._model_dir}' is missing. "
                "Run scripts\\prepare_models.ps1 while online, then start again."
            )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - environment issue
            raise SttError("faster-whisper is not installed (pip install -r requirements.txt).") from exc
        try:
            self._model = WhisperModel(
                str(self._model_dir),
                device="cpu",
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
                local_files_only=True,  # never reach the network
            )
        except Exception as exc:
            raise SttError(f"Could not load the Whisper model from '{self._model_dir}': {exc}") from exc
        logger.info(
            "Whisper model loaded from %s (cpu, %s, %d threads)",
            self._model_dir,
            self._compute_type,
            self._cpu_threads,
        )
        return self._model

    # ------------------------------------------------------------ transcribe

    def transcribe(self, audio: np.ndarray | None, cancel_event: threading.Event | None = None) -> str | None:
        """Transcribe 16 kHz mono int16 audio.

        Returns the text, or ``None`` when the input is empty, contains no
        speech, or the caller cancelled. Raises :class:`SttError` on model or
        runtime failures.
        """
        if audio is None:
            return None
        samples = np.asarray(audio).reshape(-1)
        if samples.size == 0:
            return None
        if cancel_event is not None and cancel_event.is_set():
            return None

        floats = np.clip(samples.astype(np.float32) / 32768.0, -1.0, 1.0)
        model = self._ensure_model()
        deadline = time.monotonic() + self._timeout_seconds
        started = time.monotonic()

        # One-shot command utterances: hotwords bias toward the vocabulary used
        # here, and conditioning is off so a misheard phrase cannot drag the
        # rest of the transcript along (hallucination loops on noisy clips).
        kwargs: dict[str, Any] = {
            "language": self._language,
            "beam_size": self._beam_size,
            "vad_filter": self._vad_filter,
            "condition_on_previous_text": self._condition_on_previous_text,
            "log_progress": False,
        }
        if self._hotwords:
            kwargs["hotwords"] = self._hotwords

        try:
            segments, info = model.transcribe(floats, **kwargs)
        except Exception as exc:
            raise SttError(f"Transcription failed: {exc}") from exc

        parts: list[str] = []
        try:
            for segment in segments:
                if cancel_event is not None and cancel_event.is_set():
                    logger.info("Transcription cancelled after %d segment(s)", len(parts))
                    return None
                if time.monotonic() > deadline:
                    raise SttError(f"Transcription exceeded the {self._timeout_seconds:.0f} s timeout.")
                parts.append(segment.text)
        except SttError:
            raise
        except Exception as exc:
            raise SttError(f"Transcription failed: {exc}") from exc

        text = " ".join(part.strip() for part in parts).strip()
        text = " ".join(text.split())  # collapse leftover whitespace
        elapsed = time.monotonic() - started
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if not text:
            logger.info("Transcription: no speech detected (%.2f s audio, %.2f s wall)", duration, elapsed)
            return None
        if self._debug_log_private:
            logger.info("Transcription: %r (%.2f s audio, %.2f s wall)", text, duration, elapsed)
        else:
            logger.info("Transcription: %d characters (%.2f s audio, %.2f s wall)", len(text), duration, elapsed)
        return text
