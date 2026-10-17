"""Configuration loading and validation (spec section 10).

The configuration lives in ``config/settings.json`` (JSON). A committed example
lives in ``config/settings.example.json``; ``settings.json`` itself is
git-ignored because it is machine-specific.

Path rules (portable, no hard-coded usernames):

* ``~`` at the start of a path expands to the current user's home directory.
* ``~`` means the user home, e.g. ``~/Documents``.
* Any other relative path is resolved against the project root.

Offline guardrails are enforced here: the Ollama URL must be loopback and the
model name must not be a cloud tag.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from xairex.security.policy import is_cloud_model_tag, is_loopback_url

#: Root of the whole project (the folder that contains ``xairex/``, ``config/`` …).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Default location of the runtime configuration file.
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"


class ConfigError(RuntimeError):
    """Raised when the configuration file is missing or invalid."""


class _Section(BaseModel):
    """Base for config sections: reject unknown keys so typos fail loudly."""

    model_config = ConfigDict(extra="forbid")


class AudioSettings(_Section):
    input_device: int | None = Field(
        default=None,
        description="sounddevice input device index (None = system default).",
    )
    output_device: int | None = Field(
        default=None,
        description="sounddevice output device index (None = system default).",
    )
    sample_rate: int = Field(
        default=16000,
        ge=8000,
        le=192000,
        description=(
            "Requested capture rate in Hz. The microphone module probes the "
            "device and may fall back to a supported rate and resample to 16 kHz."
        ),
    )
    frame_ms: int = Field(default=80, ge=20, le=200, description="Audio frame size in milliseconds.")
    queue_max_frames: int = Field(default=100, ge=4, le=10000, description="Bounded audio queue capacity (frames).")
    min_speech_seconds: float = Field(
        default=0.4, gt=0, le=10, description="Minimum speech duration before recording stops guessing."
    )
    silence_end_seconds: float = Field(
        default=1.2, gt=0.1, le=10, description="Trailing silence that ends a recording."
    )
    pre_roll_seconds: float = Field(default=0.3, ge=0, le=2, description="Audio kept from just before speech starts.")
    max_record_seconds: float = Field(default=15.0, gt=1, le=120, description="Hard recording duration limit.")
    speech_threshold_db: float = Field(
        default=-40.0,
        ge=-80.0,
        lt=0.0,
        description=(
            "RMS gate in dBFS: frames quieter than this count as silence for the recorder. "
            "Measured ambient floor on this laptop: p90 ~ -45 dBFS. Raise (e.g. -30) in a "
            "noisier room, lower (e.g. -50) in a very quiet one."
        ),
    )
    speech_start_frames: int = Field(
        default=2,
        ge=1,
        le=50,
        description="Consecutive voiced frames needed to start recording (suppresses clicks/pops).",
    )


class WakeWordSettings(_Section):
    enabled: bool = True
    model_path: str = "models/openwakeword/hey_jarvis_v0.1.onnx"
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    refractory_seconds: float = Field(default=1.5, ge=0.0, le=30.0, description="Minimum time between activations.")
    vad_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="openWakeWord's built-in VAD gate (0 disables it)."
    )


class SttSettings(_Section):
    #: Default model + beam measured 2026-10-16 on this machine: small.en at
    #: beam 5 transcribes a 6.2 s clip in ~2.1 s warm (base.en needed ~0.5 s but
    #: mishears fast, casual speech far more often — the owner's complaint).
    #: base.en stays available; the GUI settings window lists every local model.
    model_dir: str = "models/whisper/faster-whisper-small.en"
    model_size: str = Field(default="small", pattern="^(tiny|base|small)$")
    device: str = Field(default="cpu", pattern="^cpu$", description="CPU-only by design; GPU is prohibited.")
    compute_type: str = Field(default="int8", pattern="^(int8|float32)$")
    language: str = Field(default="en", min_length=2, max_length=8)
    beam_size: int = Field(default=5, ge=1, le=5, description="Whisper beam search width (5 = best accuracy).")
    cpu_threads: int = Field(default=4, ge=1, le=32)
    vad_filter: bool = Field(default=True, description="Use faster-whisper's bundled Silero VAD filter.")
    hotwords: str = Field(
        default="",
        description=(
            "Extra words/phrases that bias recognition (names, jargon). The command vocabulary "
            "(app names + site aliases) is added automatically; this is added on top."
        ),
    )
    condition_on_previous_text: bool = Field(
        default=False,
        description=(
            "Whisper cross-segment conditioning. Off (recommended) so one misheard phrase cannot "
            "drag the rest of a short command clip along."
        ),
    )
    timeout_seconds: float = Field(
        default=180.0,
        gt=5,
        le=1800,
        description="Soft wall-clock guard checked between transcription segments.",
    )


class TtsSettings(_Section):
    voice_path: str = "models/piper/en_US-amy-medium.onnx"
    speed: float = Field(default=1.0, gt=0.25, le=4.0, description="Speech speed multiplier (1.0 = voice default).")
    volume: float = Field(default=1.0, gt=0.0, le=1.0)


class BrainSettings(_Section):
    base_url: str = "http://127.0.0.1:11434"
    model: str = Field(
        default="xairex-fast",
        description=(
            "Ollama model name. Default is the speed profile 'xairex-fast' (qwen2.5:3b-instruct; "
            "warm answers in ~1 s on this machine). 'xairex-brain' (qwen3:4b) remains the quality "
            "profile — slower, thinking traces."
        ),
    )
    num_ctx: int = Field(default=4096, ge=512, le=32768)
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=1, le=3600)
    keep_alive: str = Field(
        default="30m",
        description="How long Ollama keeps the model loaded (e.g. '30m', '5m', '0'). Longer = fewer cold loads.",
    )
    think: bool | None = Field(
        default=None,
        description=(
            "Thinking-mode switch sent to Ollama. null = omit the field (correct for the default "
            "non-thinking speed profile). true = Qwen3 hidden reasoning (use with 'xairex-brain'; "
            "the trace is captured internally and never spoken). false = disable it — measured on "
            "the 4B: the reasoning leaks into the answer text; on 1.7b it is clean."
        ),
    )
    max_tool_rounds: int = Field(default=3, ge=0, le=10)
    history_limit: int = Field(
        default=12, ge=0, le=100, description="Maximum history messages passed back to the model."
    )
    extra_instructions: str = Field(
        default="",
        description=(
            "Extra standing instructions appended after the built-in system prompt (persona tuning "
            "that survives code updates). Keep it short — the model is small."
        ),
    )

    @field_validator("base_url")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if not is_loopback_url(value):
            raise ValueError(
                f"brain.base_url must point at the local Ollama server on loopback "
                f"(127.0.0.1 / localhost / ::1); got {value!r}. Xairex is offline-only."
            )
        return value

    @field_validator("model")
    @classmethod
    def _local_model_only(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("brain.model must not be empty.")
        if "://" in value:
            raise ValueError(f"brain.model must be a local Ollama model name, not a URL; got {value!r}.")
        if is_cloud_model_tag(value):
            raise ValueError(f"brain.model must not be a cloud model tag; got {value!r} (offline-only rule).")
        return value


class MemorySettings(_Section):
    enabled: bool = True
    database_path: str = "data/xairex.db"
    store_conversation: bool = False
    conversation_turn_limit: int = Field(default=12, ge=1, le=100)


class ToolsSettings(_Section):
    disabled: list[str] = Field(
        default_factory=list,
        description=(
            "Tool names switched off, e.g. ['wifi_control']. The same switches the "
            "settings window will toggle. Unknown names are ignored."
        ),
    )
    apps: dict[str, str] = Field(
        default_factory=dict,
        description=(
            'App name -> exe path, .lnk path or URI, e.g. {"steam": "C:/Program Files (x86)/Steam/steam.exe"}. '
            "Filled in automatically when discovery finds an app (learned); entries can also be added by hand."
        ),
    )
    browser: str = Field(default="chrome", description="Preferred browser app key for open_website.")
    website_aliases: dict[str, str] = Field(
        default_factory=dict,
        description='Extra site aliases for open_website, e.g. {"portal": "https://intranet.example.com"}.',
    )
    approved_directories: list[str] = Field(
        default_factory=lambda: ["~/Documents", "~/Desktop", "~/Downloads", "data/notes"],
        description="Directories the file tools may touch. '~' = home dir; relative paths resolve against the project root.",
    )
    volume_step_percent: int = Field(default=10, ge=1, le=50, description="Volume change per 'volume up/down' step.")
    wifi_interface: str = Field(default="", description="Wi-Fi adapter name for wifi_control (empty = first adapter).")
    read_max_bytes: int = Field(default=1_048_576, ge=1024, le=50 * 1024 * 1024)


class BridgeSettings(_Section):
    """Browser bridge (G23, D42): loopback-only WebSocket for the extension."""

    enabled: bool = Field(
        default=True,
        description=(
            "Listen on 127.0.0.1 for the Xairex browser extension (loopback only, "
            "never reachable from the network). The extension is loaded manually in Chrome/Edge."
        ),
    )
    port: int = Field(default=8769, ge=1024, le=65535, description="Loopback port the extension connects to.")
    log_dir: str = Field(
        default="data/browser",
        description="Rolling browser-activity log directory (hourly JSONL segments).",
    )
    retention_hours: float = Field(
        default=7.0,
        ge=0.5,
        le=48.0,
        description="Activity-log retention: segments older than this are auto-deleted (the owner's 7-hour rule).",
    )
    announce_messages: bool = Field(
        default=True,
        description="Let Xairex speak short notes when the extension reports a new message (rate-limited).",
    )


class AdminSettings(_Section):
    """Admin command runner (G12, D27): owner-authored templates only.

    The model can never invent command text — it may only name one of these
    pre-approved commands. Each run shows the exact command line, elevates via
    the UAC "runas" verb (one popup the owner must approve) and is audited.
    """

    commands: dict[str, str] = Field(
        default_factory=lambda: {"flush dns": "ipconfig /flushdns"},
        description=(
            "Admin commands Xairex may run — name -> exact command line, e.g. "
            '{"flush dns": "ipconfig /flushdns", "verify system files": "sfc /verifyonly"}. '
            "Only these names are accepted (never free-form text); each run gets one UAC confirmation."
        ),
    )
    timeout_seconds: int = Field(
        default=120,
        ge=15,
        le=600,
        description=(
            "How long Xairex waits for one elevated command (including the UAC prompt) before it "
            "stops waiting — the command itself keeps running."
        ),
    )


class LoggingSettings(_Section):
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    console_level: str = Field(
        default="WARNING",
        pattern="^(DEBUG|INFO|WARNING|ERROR)$",
        description=(
            "Console verbosity. WARNING keeps the styled CLI clean; the log file "
            "keeps the full 'level' detail. Set to INFO/DEBUG when troubleshooting."
        ),
    )
    file_enabled: bool = True
    file_path: str = "data/logs/xairex.log"
    debug_log_private: bool = Field(
        default=False,
        description="When true, transcripts/answers may be written to the log. Keep false unless troubleshooting.",
    )


class UiSettings(_Section):
    animations: bool = Field(
        default=True,
        description=(
            "Animated status lines (thinking/transcribing spinner, speaking wave, "
            "live microphone level meter). Only drawn in interactive terminals."
        ),
    )
    colors: str = Field(
        default="auto",
        pattern="^(auto|always|never)$",
        description="ANSI colors: 'auto' = interactive terminals only (NO_COLOR respected), 'always', 'never'.",
    )


class Settings(BaseModel):
    """Validated application settings (top-level document)."""

    model_config = ConfigDict(extra="forbid")

    audio: AudioSettings = Field(default_factory=AudioSettings)
    wake_word: WakeWordSettings = Field(default_factory=WakeWordSettings)
    stt: SttSettings = Field(default_factory=SttSettings)
    tts: TtsSettings = Field(default_factory=TtsSettings)
    brain: BrainSettings = Field(default_factory=BrainSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    bridge: BridgeSettings = Field(default_factory=BridgeSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    ui: UiSettings = Field(default_factory=UiSettings)

    #: Where this configuration was loaded from (set by load_settings; not part of the file).
    config_path: Path | None = Field(default=None, exclude=True)

    def resolve_path(self, raw: str) -> Path:
        """Resolve a configured path string to an absolute :class:`Path`.

        ``~`` expands to the user home; other relative paths resolve against
        the project root. No existence check is performed here.
        """
        expanded = Path(raw).expanduser()
        if not expanded.is_absolute():
            expanded = PROJECT_ROOT / expanded
        return expanded.resolve()


def load_settings(path: Path | str | None = None) -> Settings:
    """Load and validate settings, raising :class:`ConfigError` with a fix hint."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(
            f"Configuration file not found: {config_path}\n"
            "Create it by copying the example:\n"
            f'  Copy-Item "{PROJECT_ROOT / "config" / "settings.example.json"}" '
            f'"{DEFAULT_CONFIG_PATH}"'
        )
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration file is not valid JSON: {config_path}\n  {exc}") from exc
    # Legacy keys from earlier versions are dropped before validation. G19
    # removed tools.app_allowlist ("it must allow all", owner decision) — old
    # settings.json files must keep loading, so the key is discarded here.
    tools_section = raw.get("tools")
    if isinstance(tools_section, dict):
        tools_section.pop("app_allowlist", None)
    try:
        settings = Settings.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Configuration validation failed: {config_path}\n{exc}") from exc
    settings.config_path = config_path
    return settings


def save_settings(settings: Settings, path: Path | str | None = None) -> Path:
    """Write *settings* back to JSON atomically and return the file path.

    The document is re-serialized from the validated model (pretty-printed,
    UTF-8, ``config_path`` excluded), so a save can never smuggle unvalidated
    keys into ``settings.json``. Callers must validate their edits first — see
    :func:`xairex.gui.settings_window.merged_settings`. Defaults to the file
    the settings were loaded from.
    """
    target = Path(path) if path is not None else settings.config_path or DEFAULT_CONFIG_PATH
    payload = settings.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    settings.config_path = target
    return target
