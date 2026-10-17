# models/

Local model files live here. **They are downloaded by `scripts/prepare_models.ps1`
while the machine is online (one time), and are never committed to Git.**

Expected layout after preparation:

| Path | What it is |
|---|---|
| `whisper/faster-whisper-base/` | CTranslate2 speech-to-text model (CPU INT8) |
| `whisper/faster-whisper-base.en/` | CTranslate2 speech-to-text model (CPU INT8) — English; shipped default since D30 |
| `whisper/faster-whisper-small.en/` | CTranslate2 speech-to-text model (CPU INT8) — English; optional quality preset |
| `piper/en_US-amy-medium.onnx` + `.onnx.json` | Piper voice (female US English, 22.05 kHz) |
| `openwakeword/` | openWakeWord "hey jarvis" model + shared inference assets |
| `MANIFEST.md` | Auto-generated list: names, sources, sizes, licenses |

How to prepare (from the project root, with internet available):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_models.ps1
```

The script is idempotent: already-valid files are not re-downloaded.

Licensing notes (see `../THIRD_PARTY_NOTICES.md` for the full audit):

- openWakeWord pre-trained models (including "hey jarvis") are licensed
  **CC BY-NC-SA 4.0 — non-commercial use only**. Fine for this personal
  project; do not redistribute or use commercially.
- The Piper voice has its own license recorded in the manifest.
