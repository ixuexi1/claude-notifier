# Claude Notifier — Windows one-liner installer
# Run: irm https://.../install.ps1 | iex

$ErrorActionPreference = "Stop"
Write-Host "`n  Claude Notifier v2.0.0" -ForegroundColor Cyan
Write-Host "  Installing...`n"

# Check Python
try {
    $python = (Get-Command python -ErrorAction Stop).Source
    Write-Host "  Python: $python" -ForegroundColor Green
} catch {
    Write-Host "  Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# Install from source directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

Write-Host "  Installing package..." -ForegroundColor Gray
pip install -e "$projectDir" 2>&1 | Out-Null

Write-Host "  Enabling notifications..." -ForegroundColor Gray
cn on

Write-Host "`n  Done! Run 'cn configure' to customize, or 'cn test' to verify." -ForegroundColor Green
Write-Host "  Commands: cn on | cn off | cn test | cn status | cn sound | cn configure`n"
