#requires -Version 5.1
<#
Stage A (online): create the virtual environment and install CPU-only dependencies.

Run this ONCE while the machine has internet. The runtime never invokes it.
GPU packages (CUDA, onnxruntime-gpu, torch) are never installed and their
presence is checked and rejected at the end.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

function Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { Write-Host "`n[FAIL] $Message" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- platform ---
Step "Checking platform"
if (-not [Environment]::Is64BitOperatingSystem) { Fail "Xairex requires 64-bit Windows." }
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { Fail "This setup script supports Windows only." }
Write-Host "Windows 64-bit detected."

# ------------------------------------------------------------------ python ---
Step "Locating Python 3.12 (64-bit)"
$pythonCommand = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 -c "print('ok')" *> $null
    if ($LASTEXITCODE -eq 0) { $pythonCommand = @("py", "-3.12") }
}
if (-not $pythonCommand) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $version = (& python -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))")
        if ($version -eq "3.12") { $pythonCommand = @("python") }
    }
}
if (-not $pythonCommand) {
    Fail ("Python 3.12 (64-bit) was not found.`n" +
          "Install it first, then re-run this script:`n" +
          "  winget install Python.Python.3.12`n" +
          "or download from https://www.python.org/downloads/`n" +
          "Why 3.12: dependency wheels for ctranslate2/onnxruntime are verified on 3.12; newer Python versions may lack wheels.")
}
Write-Host "Using: $($pythonCommand -join ' ')"

# --------------------------------------------------------------- venv ---------
Step "Creating the virtual environment (.venv)"
if (Test-Path $VenvPython) {
    Write-Host ".venv already exists - reusing and updating it."
} else {
    if ($pythonCommand[0] -eq "py") {
        & py -3.12 -m venv (Join-Path $Root ".venv")
    } else {
        & python -m venv (Join-Path $Root ".venv")
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Fail "Could not create the virtual environment." }
}

# ----------------------------------------------------------- dependencies -----
Step "Installing CPU-only dependencies"
& $VenvPython -m pip install --disable-pip-version-check --upgrade pip wheel
if ($LASTEXITCODE -ne 0) { Fail "Could not upgrade pip/wheel (check your internet connection)." }

& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed - read the pip output above." }

$devRequirements = Join-Path $Root "requirements-dev.txt"
if (Test-Path $devRequirements) {
    & $VenvPython -m pip install --disable-pip-version-check -r $devRequirements
    if ($LASTEXITCODE -ne 0) { Fail "Development dependency installation failed - read the pip output above." }
}

# ------------------------------------------------------------ GPU guard -------
Step "Verifying CPU-only installation (rejecting GPU packages)"
$gpuPackages = & $VenvPython -m pip list --format=freeze | Select-String -Pattern "^(onnxruntime-gpu|torch|nvidia-)"
if ($gpuPackages) {
    Fail "GPU packages were detected and are not allowed: $gpuPackages. Remove them from .venv."
}
Write-Host "No GPU packages present."

# ------------------------------------------------------------- imports --------
Step "Verifying imports"
& $VenvPython -c "import numpy, psutil, sounddevice, ollama, pydantic; print('core imports OK')"
if ($LASTEXITCODE -ne 0) { Fail "Core imports failed." }
& $VenvPython -c "import piper, faster_whisper, openwakeword; print('voice-stack imports OK')"
if ($LASTEXITCODE -ne 0) { Fail "Voice-stack imports failed." }

# ------------------------------------------------------------- summary --------
Write-Host "`n[OK] Dependencies installed into .venv (CPU-only)." -ForegroundColor Green
Write-Host "`nNext steps (in order):"
Write-Host "  1. If Ollama is not installed yet:  winget install Ollama.Ollama"
Write-Host "  2. Copy the configuration:          Copy-Item config\settings.example.json config\settings.json"
Write-Host "  3. Prepare models (online, once):   powershell -ExecutionPolicy Bypass -File scripts\prepare_models.ps1"
Write-Host "  4. Start Xairex:                    powershell -ExecutionPolicy Bypass -File scripts\start.ps1"
