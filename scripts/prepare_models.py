"""Stage B helper: download all local model files into ``models/`` (idempotent).

Run ONLY via scripts/prepare_models.ps1 while the machine is online. This file
lives under ``scripts/`` on purpose: nothing under the ``xairex/`` runtime
package is allowed to download anything (see AGENTS.md golden rule 2).

What it does:
  1. faster-whisper models        -> models/whisper/ (base, base.en, small.en)
  2. Piper voice en_US-amy-medium -> models/piper/  (verified voice, 22.05 kHz)
  3. openWakeWord assets        -> models/openwakeword/ ("hey jarvis" stand-in + shared models; custom "Hey Xairex" model = T3.0)
  4. writes models/MANIFEST.md with file sizes and sources

Every step skips files that already exist (no unnecessary re-downloads).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

WHISPER_MODELS: list[tuple[str, str]] = [
    # (target directory under models/whisper, Hugging Face repo)
    # base.en is the runtime default: English-only models are more accurate on
    # English speech than the multilingual base (owner report 2026-10-16).
    ("faster-whisper-base", "Systran/faster-whisper-base"),
    ("faster-whisper-base.en", "Systran/faster-whisper-base.en"),
    ("faster-whisper-small.en", "Systran/faster-whisper-small.en"),
]

PIPER_REPO = "rhasspy/piper-voices"
PIPER_FILES = [
    "en/en_US/amy/medium/en_US-amy-medium.onnx",
    "en/en_US/amy/medium/en_US-amy-medium.onnx.json",
]
PIPER_TARGET = Path("piper")
PIPER_SOURCE = f"https://huggingface.co/{PIPER_REPO} (voice license: see the voice card; personal use)"

OPENWAKEWORD_TARGET = Path("openwakeword")
HEY_JARVIS_HINT = "hey_jarvis"
OPENWAKEWORD_SOURCE = (
    "https://github.com/dscripka/openWakeWord (pre-trained models: CC BY-NC-SA 4.0 - NON-COMMERCIAL, personal use only)"
)


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    files: list[tuple[str, int]] = field(default_factory=list)
    source: str | None = None


def _fail(message: str) -> Result:
    return Result(name="", ok=False, detail=message)


def _snapshot(repo: str, target: Path) -> str | None:
    """``snapshot_download`` with the older-signature fallback; error text or None."""
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(repo_id=repo, local_dir=str(target), local_dir_use_symlinks=False)
        return None
    except TypeError:
        pass
    except Exception as exc:  # noqa: BLE001
        return f"download failed: {exc}"
    try:
        snapshot_download(repo_id=repo, local_dir=str(target))
    except Exception as exc:  # noqa: BLE001 - report any download error clearly
        return f"download failed: {exc}"
    return None


def ensure_whisper_models(models_dir: Path) -> list[Result]:
    """Download the CTranslate2 conversions of Whisper (base, base.en, small.en).

    ``base.en`` is the runtime default; ``small.en`` is the quality option for
    noisy rooms or accented speech; the multilingual ``base`` stays for
    reference so existing configurations keep working.
    """
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        return [
            Result(
                name="whisper", ok=False, detail="huggingface_hub is not installed - run scripts\\install.ps1 first."
            )
        ]

    results: list[Result] = []
    for directory, repo in WHISPER_MODELS:
        target = models_dir / "whisper" / directory
        marker = target / "model.bin"
        tokenizer = target / "tokenizer.json"
        label = f"whisper ({directory})"
        source = f"https://huggingface.co/{repo} (OpenAI Whisper weights, MIT license)"
        if marker.is_file() and tokenizer.is_file():
            files = _list_files(target)
            results.append(Result(label, True, f"already present ({len(files)} files)", files, source))
            continue
        print(f"  downloading {repo} -> {target} ...")
        error = _snapshot(repo, target)
        if error:
            results.append(Result(label, False, error, [], source))
            continue
        if not (marker.is_file() and tokenizer.is_file()):
            results.append(
                Result(label, False, f"download finished but expected files are missing under {target}", [], source)
            )
            continue
        files = _list_files(target)
        results.append(Result(label, True, f"downloaded ({len(files)} files)", files, source))
    return results


def ensure_piper_voice(models_dir: Path) -> Result:
    """Fetch the verified female US English voice en_US-amy-medium (single files)."""
    target = models_dir / PIPER_TARGET
    target.mkdir(parents=True, exist_ok=True)
    expected = [target / Path(name).name for name in PIPER_FILES]
    if all(path.is_file() and path.stat().st_size > 0 for path in expected):
        files = [(path.name, path.stat().st_size) for path in expected]
        return Result("piper voice (en_US-amy-medium)", True, "already present", files, PIPER_SOURCE)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return _fail("huggingface_hub is not installed - run scripts\\install.ps1 first.")

    files = []
    try:
        for repo_path in PIPER_FILES:
            print(f"  downloading {PIPER_REPO}/{repo_path} ...")
            cached = hf_hub_download(repo_id=PIPER_REPO, filename=repo_path)
            destination = target / Path(repo_path).name
            shutil.copy2(cached, destination)
            files.append((destination.name, destination.stat().st_size))
    except Exception as exc:  # noqa: BLE001
        return _fail(f"download failed: {exc}")
    return Result("piper voice (en_US-amy-medium)", True, "downloaded", files, PIPER_SOURCE)


def _download_file(
    url: str,
    destination: Path,
    *,
    attempts: int = 10,
    connect_timeout: float = 20.0,
    read_timeout: float = 120.0,
) -> None:
    """Stream *url* to *destination* with retries (used for GitHub release assets).

    The official openWakeWord helper (``utils.download_models``) has no timeout
    and no retry; on networks that drop the occasional TCP connection it fails
    hard. This helper retries with backoff and only keeps a complete file.
    Measured on this machine: github.com drops a large fraction of new TCP
    connects, so the attempt budget is deliberately generous.
    """
    import requests

    partial = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with requests.get(url, stream=True, timeout=(connect_timeout, read_timeout)) as response:
                response.raise_for_status()
                with open(partial, "wb") as handle:
                    handle.writelines(response.iter_content(chunk_size=256 * 1024))
            partial.replace(destination)
            return
        except Exception as exc:  # noqa: BLE001 - anything network-ish is retried
            last_error = exc
            delay = min(2**attempt, 30)
            print(f"    attempt {attempt}/{attempts} failed for {destination.name}: {exc}")
            if attempt < attempts:
                print(f"    retrying in {delay}s ...")
                time.sleep(delay)
    raise RuntimeError(f"download failed after {attempts} attempts: {last_error}")


def ensure_openwakeword(models_dir: Path) -> Result:
    """Download the 'hey jarvis' wake model plus the shared ONNX inference assets.

    We deliberately fetch the official v0.5.1 release assets ourselves instead of
    calling ``openwakeword.utils.download_models``:
      * it offers no timeout/retry (flaky networks fail hard), and
      * it also downloads the tflite copies we never use (the runtime is
        ONNX-only on Windows).

    The URLs are read from the installed package's own tables
    (``FEATURE_MODELS`` / ``VAD_MODELS`` / ``MODELS``) so they cannot drift.
    """
    target = models_dir / OPENWAKEWORD_TARGET
    target.mkdir(parents=True, exist_ok=True)

    existing = sorted(p.name for p in target.glob("*.onnx"))
    if any(HEY_JARVIS_HINT in name for name in existing):
        files = [(path.name, path.stat().st_size) for path in sorted(target.glob("*.onnx"))]
        return Result("openWakeWord (hey jarvis + shared assets)", True, "already present", files, OPENWAKEWORD_SOURCE)

    try:
        from openwakeword import FEATURE_MODELS, MODELS, VAD_MODELS
    except ImportError:
        return _fail("openwakeword is not installed - run scripts\\install.ps1 first.")

    urls: list[str] = []
    for table in (FEATURE_MODELS, VAD_MODELS):
        urls.extend(str(entry["download_url"]) for entry in table.values())
    urls.append(str(MODELS["hey_jarvis"]["download_url"]))
    urls = [url.replace(".tflite", ".onnx") for url in urls]  # ONNX-only runtime

    try:
        for url in urls:
            destination = target / url.rsplit("/", 1)[-1]
            if destination.is_file() and destination.stat().st_size > 0:
                print(f"  {destination.name}: already present")
                continue
            print(f"  downloading {destination.name} ...")
            _download_file(url, destination)
    except Exception as exc:  # noqa: BLE001
        return _fail(f"download failed: {exc}")

    files = [(path.name, path.stat().st_size) for path in sorted(target.glob("*.onnx"))]
    if not any(HEY_JARVIS_HINT in name for name, _ in files):
        return _fail(f"could not find a '{HEY_JARVIS_HINT}' model after download")
    return Result(
        "openWakeWord (hey jarvis + shared assets)",
        True,
        f"ready ({len(files)} ONNX file(s))",
        files,
        OPENWAKEWORD_SOURCE,
    )


def _list_files(directory: Path) -> list[tuple[str, int]]:
    return [(path.name, path.stat().st_size) for path in sorted(directory.iterdir()) if path.is_file()]


def write_manifest(models_dir: Path, results: list[Result]) -> Path:
    lines = [
        "# models/MANIFEST.md - generated by scripts/prepare_models.py (do not commit)",
        "",
        "Sources and licensing are recorded so the audit in THIRD_PARTY_NOTICES.md stays honest.",
        "",
    ]
    for result in results:
        lines.append(f"## {result.name}")
        lines.append("")
        lines.append(f"- Status: {'OK' if result.ok else 'FAILED'} - {result.detail}")
        if result.source:
            lines.append(f"- Source: {result.source}")
        lines.append("")
        if result.files:
            lines.append("| File | Size |")
            lines.append("|---|---|")
            for name, size in result.files:
                lines.append(f"| {name} | {size:,} bytes |")
            lines.append("")
    manifest = models_dir / "MANIFEST.md"
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download Xairex model files (idempotent, online only)")
    parser.add_argument("--models-dir", required=True, help="target models directory (project models/)")
    args = parser.parse_args(argv)
    models_dir = Path(args.models_dir).resolve()
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"Preparing models in: {models_dir}")
    results: list[Result] = []
    steps = (ensure_whisper_models, ensure_piper_voice, ensure_openwakeword)
    for step in steps:
        try:
            outcome = step(models_dir)
        except Exception as exc:  # noqa: BLE001 - never crash the whole script on one model
            outcome = Result(name=step.__name__, ok=False, detail=f"unexpected error: {exc}")
        for result in outcome if isinstance(outcome, list) else [outcome]:
            results.append(result)
            marker = "OK  " if result.ok else "FAIL"
            print(f"[{marker}] {result.name}: {result.detail}")

    manifest = write_manifest(models_dir, results)
    print(f"\nManifest written: {manifest}")

    if all(result.ok for result in results):
        print("\n[OK] All model files are present.")
        return 0
    print("\n[FAIL] Some model files could not be prepared - see messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
