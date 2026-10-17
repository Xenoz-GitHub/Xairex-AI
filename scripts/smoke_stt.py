"""Manual offline smoke test: local voice round-trip (Piper -> WAV -> Whisper).

Usage (from the project root, with the venv Python):

    .\\.venv\\Scripts\\python.exe scripts\\smoke_stt.py            # synthesise + transcribe
    .\\.venv\\Scripts\\python.exe scripts\\smoke_stt.py path\\file.wav

No network access is performed or needed: Piper synthesises with the local
voice, soxr resamples to 16 kHz, faster-whisper transcribes with the local
model. Exit code 0 means the transcript roughly matches what was spoken.
"""

from __future__ import annotations

import difflib
import re
import sys
import time
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from xairex.audio.resampling import TARGET_RATE, resample_int16
from xairex.config import load_settings
from xairex.speech.synthesizer import Synthesizer
from xairex.speech.transcriber import Transcriber

PHRASE = "The quick brown fox jumps over the lazy dog."


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise SystemExit(f"[FAIL] {path}: only 16-bit PCM WAVs are supported (got {width * 8}-bit).")
    data = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return data, rate


def to_mono_int16(pcm_data: bytes, channels: int) -> np.ndarray:
    data = np.frombuffer(pcm_data, dtype=np.int16)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return data


def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z']+", text.lower()))


def main(argv: list[str]) -> int:
    settings = load_settings()
    phrase = PHRASE
    wav_path = Path(argv[1]) if len(argv) > 1 else None

    if wav_path is None:
        synthesizer = Synthesizer.from_settings(settings)
        t0 = time.perf_counter()
        pcm = synthesizer.say(phrase)
        print(f"[1] Piper synthesised {pcm.duration_seconds:.2f} s of audio in {time.perf_counter() - t0:.2f} s")
        samples = to_mono_int16(pcm.data, pcm.channels)
        rate = pcm.sample_rate
    else:
        samples, rate = read_wav(wav_path)
        phrase = ""
        print(f"[1] read {wav_path} ({len(samples) / rate:.2f} s @ {rate} Hz)")

    if rate != TARGET_RATE:
        t0 = time.perf_counter()
        samples = resample_int16(samples, rate, TARGET_RATE)
        print(f"[2] resampled {rate} Hz -> {TARGET_RATE} Hz in {time.perf_counter() - t0:.2f} s")
    else:
        print(f"[2] audio already at {TARGET_RATE} Hz")

    transcriber = Transcriber.from_settings(settings)
    t0 = time.perf_counter()
    text = transcriber.transcribe(samples)
    elapsed = time.perf_counter() - t0
    if text is None:
        print("[3] transcription returned None (no speech detected)")
        return 1
    print(f'[3] Whisper ({elapsed:.2f} s): "{text}"')

    if not phrase:
        return 0
    ratio = difflib.SequenceMatcher(None, normalise(phrase), normalise(text)).ratio()
    print(f"[4] similarity vs spoken phrase: {ratio:.0%}")
    if ratio >= 0.6:
        print("[OK] round-trip looks good")
        return 0
    print("[FAIL] transcript does not match the spoken phrase closely enough")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
