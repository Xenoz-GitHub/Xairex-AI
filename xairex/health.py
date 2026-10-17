"""Offline readiness and health checks (spec sections 9 and 13-C).

Every check is local: model files, the loopback Ollama service, audio devices
and the SQLite database. Nothing here contacts an external host. The result is
rendered for humans and used as the exit code of ``app.py --check`` and
``scripts/check_offline.ps1``.
"""

from __future__ import annotations

import importlib.util
import logging
import sqlite3
from dataclasses import dataclass, field

from xairex.config import Settings

logger = logging.getLogger("xairex.health")

#: Import name -> pip package name for everything the runtime expects.
REQUIRED_MODULES: dict[str, str] = {
    "numpy": "numpy",
    "psutil": "psutil",
    "sounddevice": "sounddevice",
    "ollama": "ollama",
    "pydantic": "pydantic",
    "piper": "piper-tts",
    "faster_whisper": "faster-whisper",
    "openwakeword": "openwakeword",
}


@dataclass
class CheckResult:
    """One named check."""

    name: str
    ok: bool
    detail: str = ""
    fix_hint: str | None = None


@dataclass
class HealthReport:
    """Ordered collection of check results."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def render(self) -> str:
        lines: list[str] = []
        for check in self.checks:
            status = "OK  " if check.ok else "FAIL"
            lines.append(f"[{status}] {check.name}: {check.detail}".rstrip())
            if not check.ok and check.fix_hint:
                lines.append(f"       fix: {check.fix_hint}")
        return "\n".join(lines)


# --------------------------------------------------------------------- checks


def check_configuration(settings: Settings) -> CheckResult:
    """Configuration was already validated when it was loaded."""
    location = settings.config_path or "defaults"
    return CheckResult("configuration", True, f"valid and loaded ({location})")


def check_dependencies() -> CheckResult:
    missing = [package for module, package in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        return CheckResult(
            "dependencies",
            False,
            "missing packages: " + ", ".join(missing),
            "Run scripts\\install.ps1 to create the virtual environment and install dependencies.",
        )
    return CheckResult("dependencies", True, "all runtime packages importable")


def check_models(settings: Settings) -> CheckResult:
    problems: list[str] = []

    stt_dir = settings.resolve_path(settings.stt.model_dir)
    if not stt_dir.is_dir() or not any(stt_dir.iterdir()):
        problems.append(f"speech-to-text model missing: {stt_dir}")

    voice = settings.resolve_path(settings.tts.voice_path)
    voice_config = voice.parent / (voice.name + ".json")
    if not voice.is_file():
        problems.append(f"Piper voice missing: {voice}")
    if not voice_config.is_file():
        problems.append(f"Piper voice config missing: {voice_config}")

    if settings.wake_word.enabled:
        wake = settings.resolve_path(settings.wake_word.model_path)
        if not wake.is_file():
            problems.append(f"wake-word model missing: {wake}")

    if problems:
        return CheckResult(
            "models",
            False,
            "; ".join(problems),
            "Run scripts\\prepare_models.ps1 while online (one time), then retry offline.",
        )
    return CheckResult("models", True, "whisper, Piper voice and wake-word files present")


def check_ollama(settings: Settings, brain: object | None = None) -> CheckResult:
    if brain is None:
        from xairex.brain.ollama_client import OllamaBrain

        brain = OllamaBrain.from_settings(settings)
    health = brain.health()  # type: ignore[attr-defined]
    if health.reachable and health.model_present:
        return CheckResult("ollama", True, health.detail)
    if not health.reachable:
        hint = "Start the local Ollama server ('ollama serve'); install Ollama first if needed (see README)."
    else:
        hint = "Run scripts\\prepare_models.ps1 to pull the models and create the local aliases."
    return CheckResult("ollama", False, health.detail, hint)


def check_audio(settings: Settings, sd: object | None = None) -> CheckResult:
    if sd is None:
        try:
            import sounddevice as sd  # type: ignore[no-redef]
        except ImportError:
            return CheckResult("audio", False, "sounddevice is not importable", "Run scripts\\install.ps1.")
    try:
        devices = sd.query_devices()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - hardware probes fail in many ways
        return CheckResult(
            "audio",
            False,
            f"could not enumerate audio devices: {exc}",
            "Check Windows sound settings and microphone privacy permissions.",
        )

    def _channels(device: object, key: str) -> int:
        if isinstance(device, dict):
            return int(device.get(key, 0) or 0)
        return int(getattr(device, key, 0) or 0)

    inputs = [d for d in devices if _channels(d, "max_input_channels") > 0]
    outputs = [d for d in devices if _channels(d, "max_output_channels") > 0]

    problems: list[str] = []
    if not inputs:
        problems.append("no microphone input detected")
    if not outputs:
        problems.append("no audio output detected")

    selected = settings.audio.input_device
    if selected is not None:
        valid = 0 <= selected < len(devices) and _channels(devices[selected], "max_input_channels") > 0
        if not valid:
            problems.append(f"configured input device index {selected} is not a usable microphone")

    if problems:
        return CheckResult(
            "audio",
            False,
            "; ".join(problems),
            "Plug in / enable the device, or set audio.input_device in config/settings.json.",
        )
    return CheckResult("audio", True, f"{len(inputs)} input device(s), {len(outputs)} output device(s)")


def check_database(settings: Settings) -> CheckResult:
    if not settings.memory.enabled:
        return CheckResult("database", True, "persistent memory disabled (nothing to check)")
    db_path = settings.resolve_path(settings.memory.database_path)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA user_version")
    except Exception as exc:  # noqa: BLE001 - any sqlite failure means the check failed
        return CheckResult(
            "database",
            False,
            f"cannot open {db_path}: {exc}",
            "Check permissions for the data directory (data/ by default).",
        )
    return CheckResult("database", True, f"SQLite reachable at {db_path}")


def run_health_checks(settings: Settings, *, brain: object | None = None, sd: object | None = None) -> HealthReport:
    """Run every check and collect the report (order matches the docs)."""
    report = HealthReport()
    report.add(check_configuration(settings))
    report.add(check_dependencies())
    report.add(check_models(settings))
    report.add(check_ollama(settings, brain=brain))
    report.add(check_audio(settings, sd=sd))
    report.add(check_database(settings))
    return report
