# Xairex Installation Guide

**One-command installation for production users.**

---

## Quick Install (Automated)

### Windows Users:

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/<yourusername>/xairex.git
   cd xairex
   ```

2. **Run the installer:**
   ```powershell
   .\scripts\setup-production.ps1
   ```

This will:
- ✅ Check/install Python 3.12
- ✅ Check/install Ollama
- ✅ Create virtual environment
- ✅ Install Python dependencies
- ✅ Download all models (Whisper, Piper, OpenWakeWord)
- ✅ Pull Ollama models (qwen2.5:3b-instruct)
- ✅ Create default config
- ✅ Run health check

**Total time:** ~10-15 minutes (depending on download speed)

---

## What Gets Installed

### 1. Python 3.12+ (if not present)
- Detected automatically
- Downloads from python.org if missing
- Sets up PATH correctly

### 2. Ollama (if not present)
- Downloads latest Windows installer
- Installs to default location
- Pulls `qwen2.5:3b-instruct` model (~2GB)

### 3. AI Models
- **Whisper** (150MB) - Speech recognition
- **Piper Amy voice** (60MB) - Text-to-speech
- **OpenWakeWord** (5MB) - Wake word detection

### 4. Python Packages
All CPU-only, no GPU requirements:
- faster-whisper
- piper-tts
- ollama-python
- And ~15 others (see `requirements.txt`)

---

## Manual Installation (Step by Step)

If the automated script fails, follow these steps:

### Step 1: Install Python 3.12+
```powershell
# Download from https://www.python.org/downloads/
# OR via winget:
winget install Python.Python.3.12
```

### Step 2: Install Ollama
```powershell
# Download from https://ollama.com/download/windows
# OR via the installer script:
.\scripts\install-ollama.ps1
```

### Step 3: Clone and Setup
```powershell
git clone https://github.com/<yourusername>/xairex.git
cd xairex

# Create virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Python packages
pip install -r requirements.txt

# Download models
.\scripts\prepare_models.ps1
```

### Step 4: Create Config
```powershell
# Copy example config
Copy-Item config\settings.example.json config\settings.json

# The defaults work for most users - edit if needed
```

### Step 5: Run Health Check
```powershell
python app.py --check
```

Should show all green checkmarks.

---

## First Run

### GUI Mode (Recommended):
```powershell
.\scripts\start.ps1 --gui
```

### CLI Mode:
```powershell
.\scripts\start.ps1
```

---

## Disk Space Requirements

- **Python:** ~100MB
- **Ollama:** ~500MB
- **AI Models:** ~2.2GB total
  - Ollama qwen2.5:3b-instruct: 2GB
  - Whisper small.en: 150MB
  - Piper Amy: 60MB
  - OpenWakeWord: 5MB
- **Total:** ~3GB

---

## Network Requirements

**During Installation:**
- Internet required to download models
- ~2.5GB total download

**After Installation:**
- ✅ **100% offline** - no internet needed
- All models run locally
- No cloud services
- No telemetry (unless you enable it)

---

## Troubleshooting

### Python not found
```powershell
# Check Python version:
py --version

# If missing, install from python.org
```

### Ollama not found
```powershell
# Check if Ollama is installed:
ollama --version

# If missing, run:
.\scripts\install-ollama.ps1
```

### Models not downloading
```powershell
# Retry model download:
.\scripts\prepare_models.ps1

# If HuggingFace is blocked, see:
# https://github.com/<yourusername>/xairex/wiki/Alternative-Model-Sources
```

### Health check fails
```powershell
# Run detailed check:
python app.py --check

# Shows exactly what's wrong
```

---

## Updating

```powershell
# Pull latest code
git pull

# Update dependencies
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --upgrade

# Update models (if new versions available)
.\scripts\prepare_models.ps1
```

---

## Uninstalling

```powershell
# 1. Delete the project folder
Remove-Item -Recurse -Force xairex\

# 2. Optionally uninstall Ollama
# Control Panel → Programs → Uninstall Ollama

# 3. Optionally remove Python
# Only if you don't use it for other things
```

---

## System Requirements

- **OS:** Windows 10/11 (64-bit)
- **CPU:** Any modern Intel/AMD (no GPU needed)
- **RAM:** 8GB minimum, 16GB recommended
- **Disk:** 3GB free space
- **Microphone:** Any USB/built-in mic
- **Speakers:** Any audio output device

---

## Support

- **Issues:** https://github.com/<yourusername>/xairex/issues
- **Wiki:** https://github.com/<yourusername>/xairex/wiki
- **Discussions:** https://github.com/<yourusername>/xairex/discussions

---

## License

[Your choice - MIT, GPL-3.0, etc.]

---

## Privacy

- ✅ 100% offline after installation
- ✅ No telemetry by default
- ✅ Your data never leaves your machine
- ⚠️ If you enable telemetry (opt-in), see Privacy Policy below
