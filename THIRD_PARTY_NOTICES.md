# Third-party notices — DRAFT

> Status: **draft**, started 2026-10-16 (Phase 1). Golden rule 8: record every
> dependency and model license as it is added. Completed and verified entry by
> entry in Phase 5, task T5.3. Items marked **VERIFY** still need a
> license-file check against the installed package (versions from
> `requirements.txt`).

## Runtime dependencies (CPU-only set, pinned in `requirements.txt`)

| Package | Version | License | Notes |
|---|---|---|---|
| pydantic | 2.14.1 | MIT | config validation |
| numpy | 2.2.6 | BSD-3-Clause | pinned below newest (see R14) |
| scipy | 1.16.3 | BSD-3-Clause | pinned below newest (see R14) |
| scikit-learn | 1.9.1 | BSD-3-Clause | openWakeWord dependency |
| onnxruntime | 1.31.0 | MIT | CPU inference (Piper, openWakeWord) |
| ctranslate2 | 4.8.3 | MIT | Whisper inference engine |
| av (PyAV) | 19.0.1 | BSD-3-Clause (VERIFY) | binary wheels bundle FFmpeg/other codecs; enumerate their licenses in T5.3 |
| psutil | 7.2.2 | BSD-3-Clause | system metrics |
| sounddevice | 0.5.6 | MIT | PortAudio wrapper (bundled PortAudio: MIT) |
| soxr | 1.1.0 | LGPL-2.1-or-later (VERIFIED 2026-10-16, `License-Expression` in installed METADATA) | resampling (Phase 2) |
| ollama (Python client) | 0.6.3 | MIT | loopback API client |
| piper-tts (`piper1-gpl`) | 1.8.0 | GPL-3.0 (VERIFY) | includes espeak-ng (GPL-3.0) phonemization; personal use fine, distribution/commercial needs care |
| faster-whisper | 1.2.1 | MIT | STT wrapper |
| openwakeword | 0.6.0 | Apache-2.0 | wake-word engine code |
| pycaw | 20260927 | MIT | master volume endpoint (set_volume tool; SAC import+function probe passed 2026-10-16) |
| comtypes | 1.4.17 | MIT | COM bridge used by pycaw |
| pytest (dev) | 9.1.1 | MIT | tests |
| ruff (dev) | 0.17.1 | MIT | linting |

Also installed and used outside the venv: **Ollama** (ollama/ollama, MIT) as a
system service, and **Windows Python 3.12** (PSF license).

## Models (downloaded by `scripts/prepare_models.ps1`; never committed)

| Model | Source | License | Notes |
|---|---|---|---|
| faster-whisper base (CTranslate2 conversion) | `Systran/faster-whisper-base` on Hugging Face | MIT (OpenAI Whisper weights) | STT |
| faster-whisper base.en (CTranslate2 conversion) | `Systran/faster-whisper-base.en` on Hugging Face | MIT (OpenAI Whisper weights) | STT — shipped default since D30 (English-only, more accurate on English speech) |
| faster-whisper small.en (CTranslate2 conversion) | `Systran/faster-whisper-small.en` on Hugging Face | MIT (OpenAI Whisper weights) | STT — optional quality preset |
| Piper voice `en_US-amy-medium` | `rhasspy/piper-voices` on Hugging Face | per-voice model card (**VERIFY** in T5.3; recorded in `models/MANIFEST.md`) | TTS, 22.05 kHz |
| openWakeWord pretrained models — **"hey jarvis"**, melspectrogram, embedding, silero VAD | openWakeWord GitHub releases (v0.5.1 assets) | **CC BY-NC-SA 4.0 — NON-COMMERCIAL** | personal use only; a blocker for any distribution/commercial use (see notes/05-DECISIONS-RISKS.md D7/R2) |
| `qwen2.5:3b-instruct` (Ollama), aliased as `xairex-fast` | Ollama library | Apache-2.0 | local LLM brain — **default speed profile** |
| `qwen3:4b` (Ollama), aliased as `xairex-brain` | Ollama library | Apache-2.0 | local LLM brain — quality profile (thinking mode) |

## Project license

Currently unpublished/private. The GPL-3.0 components (piper-tts/espeak-ng) and
the non-commercial openWakeWord models must be considered before any decision to
distribute this project — see the risk register.
