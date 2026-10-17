"""Local Piper text-to-speech (spec section 6).

Uses the documented ``piper-tts`` (piper1-gpl) Python API. The voice is loaded
once and reused. Synthesis writes a WAV into memory via ``synthesize_wav``
(fully documented API) and the raw PCM is returned for playback; long replies
are split into sentence-sized segments before synthesis.

No GPU libraries are required or used (CPU onnxruntime only).
"""

from __future__ import annotations

import io
import logging
import re
import wave
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("xairex.tts")

#: Longest synthesized segment in characters (kept modest for snappy playback).
MAX_SEGMENT_CHARS = 280


class TtsError(RuntimeError):
    """Raised when the local voice is missing or synthesis fails."""


@dataclass(frozen=True)
class Pcm:
    """Raw mono/stereo PCM audio ready for playback."""

    sample_rate: int
    channels: int
    sample_width: int  # bytes per sample (16-bit PCM -> 2)
    data: bytes

    @property
    def duration_seconds(self) -> float:
        frame_width = self.channels * self.sample_width
        if frame_width <= 0 or self.sample_rate <= 0:
            return 0.0
        return len(self.data) / frame_width / self.sample_rate


def split_text(text: str, max_chars: int = MAX_SEGMENT_CHARS) -> list[str]:
    """Split *text* into speakable segments at sentence boundaries.

    Tiny fragments are merged; over-long sentences are hard-wrapped on word
    boundaries so every returned segment fits in *max_chars*.
    """
    collapsed = " ".join(text.split())
    if not collapsed:
        return []

    pieces = re.split(r"(?<=[.!?\u2026])\s+", collapsed)
    segments: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if not current:
            current = piece
        elif len(current) + 1 + len(piece) <= max_chars:
            current = f"{current} {piece}"
        else:
            segments.append(current)
            current = piece
        while len(current) > max_chars:
            cut = current.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            segments.append(current[:cut].strip())
            current = current[cut:].strip()
    if current:
        segments.append(current)
    return segments


class Synthesizer:
    """Loads a Piper voice once and synthesizes text to PCM."""

    def __init__(
        self,
        voice_path: Path | str,
        *,
        speed: float = 1.0,
        volume: float = 1.0,
        voice: object | None = None,
    ) -> None:
        self._voice_path = Path(voice_path)
        self._speed = speed
        self._volume = volume
        self._voice = voice
        self._syn_config: object | None = None
        self._syn_config_checked = False
        self._loaded = False

    @classmethod
    def from_settings(cls, settings: object) -> Synthesizer:
        """Build from :class:`xairex.config.Settings`."""
        return cls(
            settings.resolve_path(settings.tts.voice_path),
            speed=settings.tts.speed,
            volume=settings.tts.volume,
        )

    # ------------------------------------------------------------------- load

    def load(self) -> None:
        """Check voice files and load the model (idempotent)."""
        if self._loaded:
            return
        if self._voice is None:
            onnx_path = self._voice_path
            config_path = onnx_path.parent / (onnx_path.name + ".json")
            missing = [path for path in (onnx_path, config_path) if not path.is_file()]
            if missing:
                listing = "\n  ".join(str(path) for path in missing)
                raise TtsError(
                    "Piper voice files are missing:\n  "
                    + listing
                    + "\nRun scripts\\prepare_models.ps1 (needs internet once), "
                    "or fix tts.voice_path in config/settings.json."
                )
            try:
                from piper import PiperVoice
            except ImportError as exc:
                raise TtsError("The 'piper-tts' package is not installed. Run scripts\\install.ps1.") from exc
            logger.info("Loading Piper voice: %s", onnx_path.name)
            self._voice = PiperVoice.load(str(onnx_path))
        self._loaded = True

    def _syn_config_or_none(self) -> object | None:
        """Build the SynthesisConfig once; None when unsupported or unavailable."""
        if self._syn_config is not None or self._syn_config_checked:
            return self._syn_config
        self._syn_config_checked = True
        try:
            from piper import SynthesisConfig
        except ImportError:
            return None
        try:
            # length_scale: 1.0 = voice default speed; > 1.0 is slower.
            self._syn_config = SynthesisConfig(
                volume=self._volume,
                length_scale=1.0 / self._speed,
            )
        except TypeError:  # pragma: no cover - guards against API drift
            logger.warning("This piper version rejected SynthesisConfig arguments; using voice defaults.")
            self._syn_config = None
        return self._syn_config

    # ------------------------------------------------------------------- say

    def say(self, text: str, *, max_chars: int = MAX_SEGMENT_CHARS) -> Pcm:
        """Synthesize *text* into one concatenated :class:`Pcm` (empty text -> empty Pcm)."""
        self.load()
        segments = split_text(text, max_chars=max_chars)
        if not segments:
            return Pcm(sample_rate=0, channels=0, sample_width=0, data=b"")

        chunks: list[bytes] = []
        params: tuple[int, int, int] | None = None
        for segment in segments:
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                self._synthesize_wav(segment, wav_file)
            buffer.seek(0)
            with wave.open(buffer, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                data = wav_file.readframes(wav_file.getnframes())
            if params is None:
                params = (sample_rate, channels, sample_width)
            elif (sample_rate, channels, sample_width) != params:
                logger.warning("Piper returned inconsistent audio formats; skipping segment.")
                continue
            chunks.append(data)

        if params is None:  # pragma: no cover - defensive
            return Pcm(sample_rate=0, channels=0, sample_width=0, data=b"")
        logger.debug(
            "Synthesized %d segment(s), %.2fs of audio",
            len(chunks),
            sum(len(c) for c in chunks) / (params[1] * params[2] * params[0]),
        )
        return Pcm(sample_rate=params[0], channels=params[1], sample_width=params[2], data=b"".join(chunks))

    def _synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        assert self._voice is not None  # load() guarantees this
        syn_config = self._syn_config_or_none()
        if syn_config is not None:
            try:
                self._voice.synthesize_wav(text, wav_file, syn_config=syn_config)  # type: ignore[attr-defined]
                return
            except TypeError:  # pragma: no cover - guards against API drift
                logger.warning("This piper version does not accept syn_config in synthesize_wav; using voice defaults.")
                self._syn_config = None
                self._syn_config_checked = True
        self._voice.synthesize_wav(text, wav_file)  # type: ignore[attr-defined]
