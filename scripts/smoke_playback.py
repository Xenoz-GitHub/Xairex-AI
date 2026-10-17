"""Manual offline smoke test: Piper voice -> speakers (playback path only).

Usage (from the project root, with the venv Python):

    .\\.venv\\Scripts\\python.exe scripts\\smoke_playback.py

No network access is performed or needed: Piper synthesises with the local
voice and the runtime's :class:`Playback` plays it through the default output
device. Exit code 0 means the phrase was synthesised and played to the end.
Useful after audio changes (see the 2026-10-16 bytes/numpy callback fix).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from xairex.config import load_settings
from xairex.speech.playback import Playback, PlaybackError
from xairex.speech.synthesizer import Synthesizer, TtsError

PHRASE = "Xairex playback check. One, two, three."


def main() -> int:
    settings = load_settings()

    started = time.perf_counter()
    try:
        pcm = Synthesizer.from_settings(settings).say(PHRASE)
    except TtsError as exc:
        print(f"[FAIL] synthesis: {exc}")
        return 1
    synthesized_seconds = time.perf_counter() - started
    if not pcm.data:
        print("[FAIL] synthesis returned no audio")
        return 1

    playback = Playback.from_settings(settings)
    started = time.perf_counter()
    try:
        played = playback.play(pcm)
    except PlaybackError as exc:
        print(f"[FAIL] playback: {exc}")
        return 1
    finally:
        playback.close()
    elapsed_seconds = time.perf_counter() - started

    ratio = played / pcm.duration_seconds if pcm.duration_seconds > 0 else 0.0
    print(
        f"[OK  ] synthesized {pcm.duration_seconds:.2f}s of speech in {synthesized_seconds:.2f}s; "
        f"played {played:.2f}s in {elapsed_seconds:.2f}s (ratio {ratio:.2f})"
    )
    if ratio < 0.9:
        print("[FAIL] playback ended early - audio was interrupted or cut off")
        return 1
    print('You should have heard: "Xairex playback check. One, two, three."')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
