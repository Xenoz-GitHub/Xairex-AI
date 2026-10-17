#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Xairex launcher — start the offline voice assistant.

.DESCRIPTION
    User-friendly entry point for Xairex. Runs the assistant in terminal mode
    or with the desktop GUI (--gui). All arguments are forwarded to app.py.

.PARAMETER gui
    Start the desktop GUI (Tkinter) instead of the terminal interface.

.PARAMETER check
    Run offline readiness checks and exit.

.PARAMETER config
    Path to settings.json (default: config/settings.json).

.PARAMETER version
    Show version and exit.

.EXAMPLE
    .\xairex.ps1
    Run Xairex in terminal mode.

.EXAMPLE
    .\xairex.ps1 --gui
    Start the desktop GUI.

.EXAMPLE
    .\xairex.ps1 --check
    Run offline readiness checks.
#>

param(
    [switch]$gui,
    [switch]$check,
    [switch]$version,
    [string]$config = ""
)

# Resolve paths relative to this script's directory
$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$AppPy = Join-Path $ScriptDir "app.py"

# Check that the virtual environment exists
if (-not (Test-Path $VenvPython)) {
    Write-Host "[error] Python virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "        Run scripts\install.ps1 first to set up dependencies." -ForegroundColor Red
    exit 1
}

# Build the command line
$arguments = @($AppPy)

if ($gui) {
    $arguments += "--gui"
}

if ($check) {
    $arguments += "--check"
}

if ($version) {
    $arguments += "--version"
}

if ($config) {
    $arguments += "--config"
    $arguments += $config
}

# Run app.py with the virtual environment's Python
& $VenvPython @arguments
exit $LASTEXITCODE
