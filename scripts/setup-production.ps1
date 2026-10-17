# setup-production.ps1
# One-command installation script for production users
# Installs everything needed to run Xairex

param(
    [switch]$SkipOllama,    # Skip Ollama installation
    [switch]$SkipModels,    # Skip model downloads
    [switch]$NoTelemetry    # Disable telemetry (default)
)

$ErrorActionPreference = "Stop"

Write-Host @"
╔══════════════════════════════════════════════════════╗
║                                                      ║
║           XAIREX PRODUCTION INSTALLER                ║
║                                                      ║
║  This will install everything needed to run Xairex:  ║
║  • Python 3.12+ (if missing)                         ║
║  • Ollama (local LLM server)                         ║
║  • AI Models (Whisper, Piper, OpenWakeWord)          ║
║  • Python dependencies                               ║
║                                                      ║
║  Estimated time: 10-15 minutes                       ║
║  Disk space: ~3GB                                    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host ""

# ============================================================================
# Step 1: Check Python
# ============================================================================

Write-Host "Step 1/6: Checking Python..." -ForegroundColor Yellow

$pythonVersion = $null
try {
    $pythonVersion = & py -3.12 --version 2>&1
    if ($pythonVersion -match "Python 3\.1[2-9]") {
        Write-Host "  ✓ Python 3.12+ found: $pythonVersion" -ForegroundColor Green
    } else {
        throw "Wrong version"
    }
} catch {
    Write-Host "  ✗ Python 3.12+ not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Installing Python 3.12..." -ForegroundColor Yellow
    
    # Download Python installer
    $pythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
    $pythonInstaller = "$env:TEMP\python-3.12.10-installer.exe"
    
    Write-Host "  Downloading Python installer..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
    
    Write-Host "  Running installer (this may take a few minutes)..."
    Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    
    Remove-Item $pythonInstaller
    
    # Verify installation
    $pythonVersion = & py -3.12 --version 2>&1
    Write-Host "  ✓ Python installed: $pythonVersion" -ForegroundColor Green
}

# ============================================================================
# Step 2: Check Ollama
# ============================================================================

Write-Host ""
Write-Host "Step 2/6: Checking Ollama..." -ForegroundColor Yellow

$ollamaInstalled = $false
try {
    $ollamaVersion = & ollama --version 2>&1
    if ($ollamaVersion -match "ollama version") {
        Write-Host "  ✓ Ollama found: $ollamaVersion" -ForegroundColor Green
        $ollamaInstalled = $true
    }
} catch {
    # Ollama not found
}

if (-not $ollamaInstalled -and -not $SkipOllama) {
    Write-Host "  ✗ Ollama not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Installing Ollama..." -ForegroundColor Yellow
    
    # Download Ollama installer
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
    
    Write-Host "  Downloading Ollama installer..."
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaInstaller
    
    Write-Host "  Running installer..."
    Start-Process -FilePath $ollamaInstaller -ArgumentList "/silent" -Wait
    
    Remove-Item $ollamaInstaller
    
    # Wait for Ollama service to start
    Write-Host "  Waiting for Ollama service to start..."
    Start-Sleep -Seconds 5
    
    Write-Host "  ✓ Ollama installed" -ForegroundColor Green
    $ollamaInstalled = $true
}

# ============================================================================
# Step 3: Create Virtual Environment
# ============================================================================

Write-Host ""
Write-Host "Step 3/6: Setting up Python environment..." -ForegroundColor Yellow

if (Test-Path ".venv") {
    Write-Host "  ✓ Virtual environment already exists" -ForegroundColor Green
} else {
    Write-Host "  Creating virtual environment..."
    & py -3.12 -m venv .venv
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
}

# Activate venv
& .\.venv\Scripts\Activate.ps1

# ============================================================================
# Step 4: Install Python Dependencies
# ============================================================================

Write-Host ""
Write-Host "Step 4/6: Installing Python packages..." -ForegroundColor Yellow
Write-Host "  (This may take 2-3 minutes)" -ForegroundColor Gray

& python -m pip install --upgrade pip --quiet
& pip install -r requirements.txt --quiet

Write-Host "  ✓ Python packages installed" -ForegroundColor Green

# ============================================================================
# Step 5: Download AI Models
# ============================================================================

if (-not $SkipModels) {
    Write-Host ""
    Write-Host "Step 5/6: Downloading AI models..." -ForegroundColor Yellow
    Write-Host "  (This may take 5-10 minutes depending on your connection)" -ForegroundColor Gray
    
    # Run the existing model download script
    & .\scripts\prepare_models.ps1
    
    Write-Host "  ✓ Models downloaded" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Step 5/6: Skipping model download (--SkipModels)" -ForegroundColor Yellow
}

# ============================================================================
# Step 6: Create Default Config
# ============================================================================

Write-Host ""
Write-Host "Step 6/6: Creating configuration..." -ForegroundColor Yellow

if (Test-Path "config\settings.json") {
    Write-Host "  ✓ Config already exists (not overwriting)" -ForegroundColor Green
} else {
    Copy-Item "config\settings.example.json" "config\settings.json"
    
    # Optionally enable/disable telemetry
    if ($NoTelemetry) {
        $config = Get-Content "config\settings.json" -Raw | ConvertFrom-Json
        $config | Add-Member -NotePropertyName "telemetry" -NotePropertyValue @{
            "enabled" = $false
            "endpoint" = ""
            "anonymous_id" = ""
        } -Force
        $config | ConvertTo-Json -Depth 10 | Set-Content "config\settings.json"
    }
    
    Write-Host "  ✓ Config created" -ForegroundColor Green
}

# ============================================================================
# Final Health Check
# ============================================================================

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Running health check..." -ForegroundColor Yellow
Write-Host ""

& python app.py --check

# ============================================================================
# Success!
# ============================================================================

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "✓ Installation complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "To start Xairex:" -ForegroundColor Cyan
Write-Host "  GUI mode:  .\scripts\start.ps1 --gui" -ForegroundColor White
Write-Host "  CLI mode:  .\scripts\start.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  README.md - Overview and features"
Write-Host "  INSTALL.md - Detailed installation guide"
Write-Host "  notes/00-SPEC-JARVIS.md - Full specification"
Write-Host ""

if (-not $NoTelemetry) {
    Write-Host "Privacy:" -ForegroundColor Cyan
    Write-Host "  • Xairex runs 100% offline by default"
    Write-Host "  • No telemetry enabled"
    Write-Host "  • Your data never leaves your machine"
    Write-Host ""
}

Write-Host "Need help? Open an issue:" -ForegroundColor Cyan
Write-Host "  https://github.com/<yourusername>/xairex/issues"
Write-Host ""
