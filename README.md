# Xairex — offline voice assistant (Windows, CPU-only)

A personal, **fully offline** voice assistant for this Windows laptop. No cloud
services, no telemetry, no downloads at runtime — Xairex talks only to a local
Ollama model (loopback), local files and local audio devices.

> **Current status: Phase 2 accepted · Phase G underway** — typed questions *and* the voice loop
> (push-to-talk: microphone → local Whisper → local brain → local voice) work end-to-end,
> now on the **speed profile** (warm answers ≈ 1 s instead of 40–70 s). Next: the desktop GUI
> and OS-control tools (Phase G), then the "Hey Xairex" wake word. Progress lives in
> [`notes/03-TASKS.md`](notes/03-TASKS.md).

---

## What works today

| Feature | Status |
|---|---|
| Local brain: Ollama — speed profile `qwen2.5:3b-instruct` (alias `xairex-fast`), quality profile `qwen3:4b` (alias `xairex-brain`); loopback-only | ✅ Phase 1 · speed profile 2026-10-16 |
| Local voice: Piper `en_US-amy-medium`, CPU-only inference | ✅ Phase 1 |
| Typed terminal: `ask <text>` → spoken + printed answer | ✅ Phase 1 |
| `say <text>` (speak arbitrary text), `stop` (interrupt instantly), `health` | ✅ Phase 1 |
| Preflight health checks (`check_offline.ps1`): config, deps, models, Ollama, audio, SQLite | ✅ Phase 1 |
| Config file with strict validation + offline guardrails (loopback URL, no `-cloud` models) | ✅ Phase 1 |
| Explicit state machine, logging with privacy gate, per-request metrics | ✅ Phase 1 |
| Offline test suite (mocked hardware/Ollama; network calls fail tests loudly) | ✅ 188 tests passing |
| Push-to-talk: Enter (or `ptt`) → mic capture + endpointing → local Whisper → spoken answer | ✅ Phase 2 |
| "Hey Xairex" wake word (custom-trained model), chime, hands-free standby | 🔜 after Phase G |
| Desktop GUI (Tkinter): chat pane, TALK/STOP, animated status orb, metrics footer (`--gui`) | ✅ Phase G (G1–G3) |
| OS-control tools (open app/website, volume, media, Wi-Fi best-effort) + no-LLM fast router | 🔜 Phase G (G5–G7) |
| Safe tools (time, CPU/RAM, files) + SQLite memory | 🔜 later phases |

## Machine requirements

- Windows 10/11, 64-bit (tested on Intel i5-13420H, 15.7 GB RAM)
- **Python 3.12** (exact — dependency wheels are verified on it)
- [Ollama for Windows](https://ollama.com/download) (installed separately, runs locally)
- ~5 GB free disk space for the Ollama models (fast + quality profiles); a microphone + speakers for the voice phases
- Internet **only** during setup (Stages A and B below); runtime is offline

## Setup (three stages)

Run everything from the project root. PowerShell may need
`-ExecutionPolicy Bypass` when invoking the scripts.

### Stage A — install dependencies (needs internet, run once)

```powershell
# If Python 3.12 is missing:  winget install Python.Python.3.12
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Creates `.venv`, installs the pinned CPU-only dependency set, rejects GPU
packages if any sneak in, and import-checks the stack.

### Stage B — prepare models (needs internet, run once)

```powershell
# Ollama (if not installed yet):  winget install Ollama.Ollama
Copy-Item config\settings.example.json config\settings.json
powershell -ExecutionPolicy Bypass -File scripts\prepare_models.ps1
```

Downloads into `models\`: the Whisper base STT model, the Piper voice, and the
openWakeWord assets (the pretrained "hey jarvis" model stands in until the custom "Hey Xairex" wake model is trained — idempotent, safe to re-run). Also pulls
`qwen2.5:3b-instruct` + `qwen3:4b` in Ollama and creates the local aliases `xairex-fast`
(default speed profile) and `xairex-brain` (quality profile). Writes
`models\MANIFEST.md`.

### Stage C — run (fully offline — disconnect Wi-Fi to prove it)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_offline.ps1   # optional readiness check
powershell -ExecutionPolicy Bypass -File scripts\start.ps1            # terminal mode
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 --gui      # desktop GUI (Tkinter)
```

Nothing in Stage C downloads anything: `app.py` and everything under `xairex\`
are offline by design (see "Offline guarantees" below).

## Using it (Phases 1–2)

```
you> ask What is the capital of France?
you> [press Enter]                  (then speak: push-to-talk, stops after you pause)
you> tell me a joke                 (bare sentences also count as questions)
you> say Testing one two three      (speak text directly, no model involved)
you> stop                           (interrupt the current answer immediately)
you> open youtube in chrome         (OS commands run with no model at all)
you> volume up | volume 40 | mute   (system volume — pycaw)
you> turn off wifi | wifi status    (toggle needs admin; else the Settings pane opens)
you> play/pause | next track        (media keys)
you> what time is it | cpu usage    (machine status, instantly)
you> find my tax documents          (searches your approved folders)
you> health                         (re-run the readiness checks)
you> quit                           (Ctrl+C works too)
```

The answer is printed and spoken through the local Piper voice. Push-to-talk
records locally, transcribes with the local Whisper model and never sends audio
anywhere. If the room is noisy, tune `audio.speech_threshold_db` and
`audio.speech_start_frames` in `config\settings.json` (see D18 in the notes).

The terminal shows a cyber-styled skin (banner, colors, animated phases: a
spinner while thinking/transcribing, a wave while speaking, and a live
microphone level meter while push-to-talk records) — D21. Animations and
colors appear only in a real interactive terminal; redirected output stays
plain so scripts and logs remain readable.

## OS control & tools (Phase G)

Xairex can run a small set of **typed tools** — never arbitrary commands:

- `open_app` — Chrome/Edge/Firefox, Notepad, Calculator, Explorer, Settings, Task Manager, VS Code, Spotify… (extend via `tools.apps` + `tools.app_allowlist`)
- `open_website` — youtube/google/gmail/github/maps/… aliases or any `https://` address (opens in `tools.browser`)
- `set_volume` (up/down/set/mute/status) and `media_control` (play/pause/next/previous)
- `wifi_control` — on/off/status; Windows needs admin rights for the toggle, otherwise the Wi-Fi settings pane opens (D24)
- `system_info` (time, date, CPU, memory, disk, battery) and `find_files` (search inside `tools.approved_directories`)

Common phrasings are matched by a **no-LLM fast router** (action in well under a
second); everything else goes to the local model with the same tools attached.
Every execution is schema-validated, time-bounded and logged to the `tool_runs`
table in `data\xairex.db`. Switch any tool off via `tools.disabled` in
`config\settings.json` (a toggles window is G4; file-management, admin-command,
Defender-scan and memory tools are G11–G15).

## Desktop GUI

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 --gui
# or directly:  .\.venv\Scripts\python.exe app.py --gui
```

The Tkinter window (stdlib only, zero new dependencies — D22/D25) shows the
chat transcript (with the startup health report), a question box (type, press
Enter), **TALK** for push-to-talk, **STOP** to interrupt an answer instantly,
**HEALTH** to re-run the offline checks, and **CLEAR** to wipe the transcript.
The status orb animates per phase: idle pulse → level-reactive ring while
recording → rotating ring while thinking/transcribing → wave while speaking →
red flash on error. The side panel shows the current phase and the last
request's metrics (`llm=…ms total=…ms rss=…`). Same engine, same local
pipeline as the terminal — just a different front end.

## Configuration

Edit `config\settings.json` (created from `config\settings.example.json`).
Every key is optional. Highlights:

| Key | Meaning |
|---|---|
| `audio.input_device` / `output_device` | sounddevice indices (`null` = system default) |
| `tts.voice_path`, `tts.speed`, `tts.volume` | voice file and speaking style |
| `brain.base_url`, `brain.model` | must stay **loopback** and **non-cloud**; the file rejects anything else |
| `brain.num_ctx`, `brain.temperature`, `brain.timeout_seconds`, `brain.keep_alive` | local model behaviour |
| `stt.model_dir`, `stt.compute_type` | local Whisper model location; `int8` on CPU |
| `ui.animations`, `ui.colors` | CLI skin: animations on/off; colors `auto`/`always`/`never` (honours `NO_COLOR`) |
| `logging.level`, `logging.console_level` | file verbosity vs console verbosity (console defaults to `WARNING` for a clean CLI) |
| `logging.debug_log_private` | `false` by default: transcripts/answers are **not** written to the log |

Path rules: `~` expands to your home directory; other relative paths resolve
against the project root. Unknown keys, out-of-range values, non-loopback URLs
and `-cloud` model tags are rejected with actionable errors.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite needs **no internet, no models, no microphone and no GPU** — every
test runs against fakes, and an autouse fixture fails any test that tries to
open a non-loopback connection.

## Offline guarantees (why you can trust "no cloud")

- The runtime only ever contacts `127.0.0.1` / `localhost` / `::1` (enforced in
  the config validator *and* the brain client constructor).
- Cloud model tags (`…-cloud`) are rejected in configuration.
- All model files are downloaded once by `scripts\prepare_models.ps1`; the
  runtime never downloads — missing files produce clear errors instead.
- GPU packages (CUDA, `onnxruntime-gpu`, `torch`) are never installed or used;
  `install.ps1` verifies their absence.
- Model output is never `eval`ed/`exec`ed; tools (Phase 4) will run only through
  a typed registry with fixed allowlists.

Full rules and architecture: [`AGENTS.md`](AGENTS.md) and
[`notes/02-ARCHITECTURE.md`](notes/02-ARCHITECTURE.md).

## Project layout

```
app.py                  entry point (--check, --config, --version)
xairex/                 runtime package (never downloads anything)
  config.py             settings model + validation + offline guardrails
  logging_config.py     console/file logging, private-content gate
  state_machine.py      explicit states + transition table
  metrics.py            per-request timings
  health.py             offline readiness checks
  runtime.py            engine thread + terminal interface
  brain/                Ollama client, prompts, conversation history
  speech/               Piper synthesis + speaker playback
  audio/                (Phase 2-3) microphone, resampling, wake word
  tools/                (Phase 4) typed tool registry
  memory/               (Phase 4) SQLite persistence
  security/             offline policy helpers, path validation
scripts/                install / prepare_models / start / check_offline
config/                 settings.example.json (settings.json is git-ignored)
models/                 local model files (git-ignored; see models/README.md)
data/                   SQLite db + logs (git-ignored)
notes/                  agent handoff notes — read this first
tests/                  offline test suite
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Configuration file not found` | `Copy-Item config\settings.example.json config\settings.json` |
| `Ollama is not running` | Start Ollama (`ollama serve` runs it; the Windows app starts it automatically). |
| `Local model '…' is missing` | Run `scripts\prepare_models.ps1` (it pulls the models and creates the local aliases). |
| `Piper voice files are missing` | Run `scripts\prepare_models.ps1`. |
| Answers are printed but not spoken | The voice files or output device are missing — run `check_offline.ps1` and read the failed checks. |
| `An Application Control policy has blocked this file` (ImportError, `DLL load failed`) | Microsoft **Smart App Control** can block brand-new unsigned binaries. The pinned versions in `requirements.txt` are known to load on this machine. If it reappears after adding dependencies, wait a few minutes and retry once; persistent blocks need older pins or Smart App Control turned off (your call — it is a one-way security setting). See `notes/05-DECISIONS-RISKS.md` R14. |
| Tests fail with "Network access ... blocked" | That's the offline guard working: a test tried to reach a non-loopback host. It must be mocked. |

## Roadmap

All phases — the active Phase G (desktop GUI, OS-control tools, fast command router,
responsiveness), then wake word, tools + memory, hardening + documentation —
are tracked with checkboxes in [`notes/03-TASKS.md`](notes/03-TASKS.md).

## Licensing

This is a personal, non-commercial project. Notable dependencies: Whisper
weights (MIT), Qwen2.5 + Qwen3 (Apache-2.0), Piper (`piper1-gpl`, GPL-3.0 + espeak-ng),
openWakeWord code (Apache-2.0) — but its pretrained models, **including
"hey jarvis", are CC BY-NC-SA 4.0 (non-commercial)**. Details and the full
draft audit: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
