#requires -Version 5.1
<#
Offline readiness check (spec section 13-C).

Verifies configuration, dependencies, model files, the LOCAL Ollama service,
audio devices and the database. It makes no external network calls - only the
loopback check against 127.0.0.1 for Ollama.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\check_offline.ps1
Exit code 0 = everything ready; 1 = something needs attention.
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[FAIL] Virtual environment not found (.venv). Run scripts\install.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Xairex offline readiness check (all checks are local):" -ForegroundColor Cyan
& $VenvPython (Join-Path $Root "app.py") --check

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] Everything needed for offline operation is present." -ForegroundColor Green
} else {
    Write-Host "`n[FAIL] Not fully ready - fix the items marked FAIL above (see hints)." -ForegroundColor Yellow
}
exit $LASTEXITCODE
