#requires -Version 5.1
<#
Stage B (online): prepare all local models. Run while the machine has internet.

  1. Ollama: pull qwen2.5:3b-instruct (create 'xairex-fast' alias) + qwen3:4b (create 'xairex-brain' alias)
  2. Python-side downloads into models\: whisper, Piper voice, openWakeWord
  3. Verification via 'app.py --check'

Idempotent: already-valid files are not re-downloaded. The runtime never calls
this script.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\prepare_models.ps1
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

function Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Warn([string]$Message) { Write-Host "[warn] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "`n[FAIL] $Message" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $VenvPython)) {
    Fail "The virtual environment was not found. Run scripts\install.ps1 first."
}

$failed = $false

# ------------------------------------------------------------ 1. Ollama -------
Step "1/3  Ollama models (speed profile 'xairex-fast' + quality profile 'xairex-brain')"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Warn "Ollama is not installed or not on PATH. Install it (e.g. 'winget install Ollama.Ollama'), then re-run this script."
    $failed = $true
} else {
    Write-Host "Pulling the fast model 'qwen2.5:3b-instruct'..."
    & ollama pull qwen2.5:3b-instruct
    if ($LASTEXITCODE -ne 0) {
        Warn "ollama pull qwen2.5:3b-instruct failed - check that the Ollama server is running."
        $failed = $true
    } else {
        Write-Host "Creating model alias 'xairex-fast'..."
        $modelfile = Join-Path $env:TEMP "xairex-fast.Modelfile"
        "FROM qwen2.5:3b-instruct" | Set-Content -Path $modelfile -Encoding ASCII
        & ollama create xairex-fast -f $modelfile
        if ($LASTEXITCODE -ne 0) {
            Warn "ollama create xairex-fast failed."
            $failed = $true
        }
        Remove-Item $modelfile -ErrorAction SilentlyContinue
    }

    Write-Host "Pulling the quality model 'qwen3:4b' (optional)..."
    & ollama pull qwen3:4b
    if ($LASTEXITCODE -ne 0) {
        Warn "ollama pull qwen3:4b failed (optional quality profile - the fast profile still works)."
    } else {
        Write-Host "Creating model alias 'xairex-brain'..."
        $modelfile = Join-Path $env:TEMP "xairex-brain.Modelfile"
        "FROM qwen3:4b" | Set-Content -Path $modelfile -Encoding ASCII
        & ollama create xairex-brain -f $modelfile
        if ($LASTEXITCODE -ne 0) {
            Warn "ollama create xairex-brain failed (optional quality profile)."
        }
        Remove-Item $modelfile -ErrorAction SilentlyContinue
    }
}

# --------------------------------------------------- 2. Python-side models ----
Step "2/3  Downloading model files into the project (whisper, Piper voice, openWakeWord)"
& $VenvPython (Join-Path $PSScriptRoot "prepare_models.py") --models-dir (Join-Path $Root "models")
if ($LASTEXITCODE -ne 0) {
    Warn "Some model files could not be prepared - see the messages above."
    $failed = $true
}

# ---------------------------------------------------------- 3. Verification ---
Step "3/3  Offline readiness check"
& $VenvPython (Join-Path $Root "app.py") --check
if ($LASTEXITCODE -ne 0) {
    Warn "Readiness check reported problems (see above). If the only failure is Ollama, start it and re-run."
    $failed = $true
}

if ($failed) {
    Write-Host "`n[PARTIAL] Preparation finished with problems - fix the warnings above and re-run." -ForegroundColor Yellow
    exit 1
}
Write-Host "`n[OK] All models prepared. Start Xairex with scripts\start.ps1" -ForegroundColor Green
