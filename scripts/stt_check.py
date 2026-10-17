"""Manual offline A/B check: which Whisper model hears *your* voice best?

Usage (project root, venv python):

    .\\.venv\\Scripts\\python.exe scripts\\stt_check.py                 # record once, compare every local model
    .\\.venv\\Scripts\\python.exe scripts\\stt_check.py --times 3       # allow up to three recordings
    .\\.venv\\Scripts\\python.exe scripts\\stt_check.py --models base.en,small.en
    .\\.venv\\Scripts\\python.exe scripts\\stt_check.py --replay data\\stt-check\\some.wav

For every recording the script transcribes the same audio with each installed
model (models/whisper/*), with and without the command hotwords, and shows what
the fast router would do with each transcript. The recording is saved under
data/stt-check/ so it can be replayed later.

Fully offline: local microphone, local models, no network access.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from xairex.audio.microphone import Microphone, MicrophoneError
from xairex.audio.recorder import Recorder
from xairex.audio.resampling import TARGET_RATE, StreamResampler, resample_int16
from xairex.config import Settings, load_settings
from xairex.router import route
from xairex.speech.transcriber import Transcriber, default_hotwords

CHECK_DIR = PROJECT_ROOT / "data" / "stt-check"


def available_models(settings: Settings, wanted: list[str] | None) -> list[tuple[str, Path]]:
    """Local Whisper model dirs, as (short label, path), filtered when asked."""
    found: list[tuple[str, Path]] = []
    whisper_root = settings.resolve_path("models/whisper")
    for directory in sorted(whisper_root.glob("faster-whisper-*")):
        if not (directory / "model.bin").is_file() or not (directory / "tokenizer.json").is_file():
            continue
        label = directory.name.removeprefix("faster-whisper-")
        if wanted is not None and label not in wanted:
            continue
        found.append((label, directory))
    return found


def record_utterance(settings: Settings, wait_seconds: float) -> np.ndarray | None:
    """Capture one spoken utterance through the real pipeline (mic -> 16 kHz)."""
    try:
        microphone = Microphone.from_settings(settings)
        microphone.open()
    except MicrophoneError as exc:
        print(f"[mic] {exc}")
        return None
    resampler = StreamResampler(microphone.device_rate, TARGET_RATE)
    recorder = Recorder.from_settings(settings)
    deadline = time.monotonic() + wait_seconds
    try:
        microphone.drain()
        print(f"[mic] listening on '{microphone.device_name}' — speak now ({wait_seconds:.0f} s max wait)...")
        while True:
            frame = microphone.read_frame(timeout=0.2)
            if frame is None:
                if not recorder.is_recording and time.monotonic() > deadline:
                    print("[mic] nothing heard — the microphone level may be low (check Windows sound settings).")
                    return None
                continue
            utterance = recorder.feed(resampler.process(frame))
            if utterance is not None:
                return utterance
            if not recorder.is_recording and time.monotonic() > deadline:
                print("[mic] nothing heard — the microphone level may be low (check Windows sound settings).")
                return None
    except KeyboardInterrupt:
        print("\n[mic] cancelled.")
        return None
    finally:
        microphone.close()


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


def save_wav(samples: np.ndarray) -> Path:
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECK_DIR / time.strftime("rec-%Y%m%d-%H%M%S.wav")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(TARGET_RATE)
        handle.writeframes(samples.tobytes())
    return path


def peak_dbfs(samples: np.ndarray) -> float:
    peak = int(np.max(np.abs(samples.astype(np.int32)))) if len(samples) else 0
    return 20.0 * np.log10(peak / 32768.0) if peak else -120.0


def compare(
    samples: np.ndarray,
    settings: Settings,
    models: list[tuple[str, Path]],
) -> None:
    """Transcribe *samples* with every model x hotwords combination and print a table.

    One model instance is loaded at a time (and freed before the next), because
    ctranslate2 instances in the same process contend over OpenMP threads and
    skew the timings. ``first`` includes the model load; ``warm`` is the real
    per-utterance cost once the model is resident.
    """
    hotwords = default_hotwords(settings)
    default_dir = Path(str(settings.resolve_path(settings.stt.model_dir))).name
    duration = len(samples) / TARGET_RATE
    peak = peak_dbfs(samples)
    print(f"[audio] {duration:.2f} s, peak {peak:.1f} dBFS ({'suspiciously quiet' if peak < -35 else 'level ok'})")
    print()
    print(f"{'model':<10} {'hotwords':<9} {'load':>6} {'warm':>6}  transcript")
    for label, model_dir in models:
        is_default = model_dir.name == default_dir
        for use_hotwords in (True, False):
            transcriber = Transcriber(model_dir, hotwords=hotwords if use_hotwords else "")
            started = time.perf_counter()
            transcriber.transcribe(samples)
            first = time.perf_counter() - started
            started = time.perf_counter()
            text = transcriber.transcribe(samples)
            warm = time.perf_counter() - started
            marker = " *" if is_default and use_hotwords else ""
            shown = f'"{text}"' if text else "(nothing recognised)"
            print(f"{label:<10} {'on' if use_hotwords else 'off':<9} {first:>5.2f}s {warm:>5.2f}s  {shown}{marker}")
            if text:
                routed = route(text, settings)
                if routed is not None:
                    print(f"{'':<35}-> router: {routed.tool} {routed.arguments}")
                else:
                    print(f"{'':<35}-> router: no match (would go to the LLM)")
            del transcriber
            gc.collect()
    print()
    print("* = the setting Xairex currently runs with (stt.model_dir + hotwords).")
    print("  Timings vary with laptop power state; compare the transcripts first.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Offline STT A/B check for Xairex.")
    parser.add_argument("--replay", type=Path, default=None, help="compare a saved WAV instead of recording")
    parser.add_argument("--models", default=None, help="comma list: base,base.en,small.en (default: all found)")
    parser.add_argument("--times", type=int, default=0, help="max recordings in one run (0 = until you quit)")
    parser.add_argument("--wait", type=float, default=8.0, help="seconds to wait for speech to start (default 8)")
    args = parser.parse_args(argv[1:])

    settings = load_settings()
    wanted = [part.strip() for part in args.models.split(",")] if args.models else None
    models = available_models(settings, wanted)
    if not models:
        print(f"[FAIL] no local Whisper models found under {settings.resolve_path('models/whisper')}.")
        print("       Run scripts\\prepare_models.ps1 while online to download them.")
        return 1

    print(f"models: {', '.join(label for label, _ in models)}")
    print(f"default model_dir: {settings.stt.model_dir}")

    if args.replay is not None:
        samples, rate = read_wav(args.replay)
        if rate != TARGET_RATE:
            samples = resample_int16(samples, rate, TARGET_RATE)
        print(f"[audio] replayed {args.replay}")
        compare(samples, settings, models)
        return 0

    rounds = 0
    while True:
        if rounds:
            answer = input("[Enter] = record another   [q] = quit > ").strip().lower()
            if answer in ("q", "quit", "exit"):
                break
        rounds += 1
        samples = record_utterance(settings, args.wait)
        if samples is not None and len(samples):
            path = save_wav(samples)
            print(f"[save] {path.relative_to(PROJECT_ROOT)}")
            compare(samples, settings, models)
        if args.times and rounds >= args.times:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
