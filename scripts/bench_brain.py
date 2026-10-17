"""Manual speed benchmark for local brain models (owner request: 2-3 s answers).

Usage (from the project root, with the venv Python):

    .\\.venv\\Scripts\\python.exe scripts\\bench_brain.py
    .\\.venv\\Scripts\\python.exe scripts\\bench_brain.py --no-reference

For every candidate (plus the current ``xairex-brain`` reference) it measures:

* **cold** - seconds for the first call after a best-effort unload;
* **warm** - seconds per prompt for four representative short-answer prompts;
* **length** - characters in each answer (speed is judged together with quality).

It prints a summary table, every answer for manual review, and writes a JSON
report under ``data/bench/``. Models that are not pulled locally are reported
and skipped. Nothing here downloads anything - it only talks to local Ollama.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from xairex.brain.ollama_client import BrainError, OllamaBrain
from xairex.brain.prompts import XAIREX_SYSTEM_PROMPT

OLLAMA_HOST = "http://127.0.0.1:11434"

# (model tag, think flag) - None omits the flag for models without thinking mode
CANDIDATES: list[tuple[str, bool | None]] = [
    ("xairex-brain", True),
    ("qwen3:1.7b", True),
    ("qwen3:1.7b", False),
    ("llama3.2:3b", None),
    ("qwen2.5:3b-instruct", None),
]

PROMPTS = [
    "In one short sentence, what is the capital of France?",
    "Tell me one short fun fact about octopuses.",
    "What is 17 times 24? Reply with just the number.",
    "Introduce yourself as Xairex in one short sentence.",
]


def _present(names: set[str], model: str) -> bool:
    return model in names or f"{model}:latest" in names


def _unload(client: object, model: str) -> None:
    """Best-effort immediate unload so the next call can be timed cold."""
    try:
        client.generate(model=model, prompt="", keep_alive=0)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - best effort; a warm first call is still informative
        print(f"  note: could not unload {model} first ({type(exc).__name__})")


def _bench_config(model: str, think: bool | None) -> dict:
    label = f"{model} (think={'omitted' if think is None else think})"
    print(f"\n--- {label} ---")
    brain = OllamaBrain(base_url=OLLAMA_HOST, model=model, timeout_seconds=300.0, think=think)

    rows: list[dict] = []
    for index, prompt in enumerate(PROMPTS, start=1):
        messages = [
            {"role": "system", "content": XAIREX_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        started = time.perf_counter()
        try:
            reply = brain.chat(messages)
        except BrainError as exc:
            rows.append({"prompt": prompt, "seconds": None, "error": str(exc)})
            print(f"  call {index}/{len(PROMPTS)} FAILED: {exc}")
            continue
        seconds = time.perf_counter() - started
        content = reply.content.strip()
        thinking_chars = len((reply.thinking or "").strip())
        rows.append(
            {"prompt": prompt, "seconds": round(seconds, 2), "content": content, "thinking_chars": thinking_chars}
        )
        marker = "cold" if index == 1 else "warm"
        print(f"  {marker} {seconds:6.1f}s  {len(content):4d} chars  thinking {thinking_chars:5d}  {content[:88]!r}")
    brain.close()

    warm = [row["seconds"] for row in rows[1:] if row.get("seconds") is not None]
    return {
        "model": model,
        "think": think,
        "cold_seconds": rows[0].get("seconds") if rows else None,
        "warm_median_seconds": round(sorted(warm)[len(warm) // 2], 2) if warm else None,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark local brain models for Xairex.")
    parser.add_argument("--no-reference", action="store_true", help="skip the current xairex-brain reference run")
    args = parser.parse_args()

    try:
        import ollama
    except ImportError:
        print("[FAIL] the 'ollama' package is missing - run scripts\\install.ps1")
        return 1

    client = ollama.Client(host=OLLAMA_HOST, timeout=30)
    try:
        listing = client.list()
    except Exception as exc:  # noqa: BLE001 - report and exit
        print(f"[FAIL] Ollama is not reachable at {OLLAMA_HOST}: {exc}")
        return 1

    entries = listing.get("models", []) if isinstance(listing, dict) else getattr(listing, "models", [])
    names: set[str] = set()
    for entry in entries or []:
        name = entry.get("model") if isinstance(entry, dict) else getattr(entry, "model", None)
        if name:
            names.add(str(name))
    print(f"local models: {', '.join(sorted(names)) or 'none'}")

    configs = [c for c in CANDIDATES if not (args.no_reference and c[0] == "xairex-brain")]
    reports: list[dict] = []
    for model, think in configs:
        if not _present(names, model):
            print(f"\n--- {model}: not pulled locally - skipped (run: ollama pull {model}) ---")
            continue
        _unload(client, model)
        reports.append(_bench_config(model, think))

    if not reports:
        print("[FAIL] nothing to benchmark - pull the candidates first")
        return 1

    print("\n================ summary ================")
    print(f"{'model':<24} {'think':>8} {'cold s':>8} {'warm median s':>14}")
    for report in reports:
        cold = report["cold_seconds"]
        warm = report["warm_median_seconds"]
        cold_text = "-" if cold is None else f"{cold:.1f}"
        warm_text = "-" if warm is None else f"{warm:.1f}"
        print(f"{report['model']:<24} {report['think']!s:>8} {cold_text:>8} {warm_text:>14}")

    out_dir = PROJECT_ROOT / "data" / "bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"bench-{stamp}.json"
    out_path.write_text(json.dumps({"host": OLLAMA_HOST, "reports": reports}, indent=2), encoding="utf-8")
    print(f"\nreport: {out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[stopped]")
        raise SystemExit(130)
