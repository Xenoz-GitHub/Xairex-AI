#requires -Version 5.1
<#
Stage C (offline): start Xairex.

This script NEVER downloads, updates or installs anything. It only:
  1. checks the virtual environment and configuration exist
  2. starts the application

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 --check   (readiness report only)
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[FAIL] Virtual environment not found (.venv)." -ForegroundColor Red
    Write-Host "Run scripts\install.ps1 once while online, then try again."
    exit 1
}

$config = Join-Path $Root "config\settings.json"
if (-not (Test-Path $config)) {
    Write-Host "[FAIL] Configuration not found: config\settings.json" -ForegroundColor Red
    Write-Host "Create it from the example (no changes required for defaults):"
    Write-Host "  Copy-Item config\settings.example.json config\settings.json"
    exit 1
}

& $VenvPython (Join-Path $Root "app.py") @args
exit $LASTEXITCODE
