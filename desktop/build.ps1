# build.ps1 — Build and package the Electron desktop app for Windows.
# Run from the desktop/ directory.
# Prerequisites: Node.js installed, run `npm install` first.

$ErrorActionPreference = "Stop"
$DESKTOP = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=== LegalAcct AI — Desktop Builder ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build the frontend
Write-Host "[1/3] Building React frontend..." -ForegroundColor Green
Set-Location (Join-Path $DESKTOP "..\frontend")
& npm run build
if ($LASTEXITCODE -ne 0) { Write-Host "Frontend build failed." -ForegroundColor Red; exit 1 }

# Step 2: Install Electron deps
Write-Host "[2/3] Installing desktop dependencies..." -ForegroundColor Green
Set-Location $DESKTOP
& npm install
if ($LASTEXITCODE -ne 0) { Write-Host "npm install failed." -ForegroundColor Red; exit 1 }

# Step 3: Package with electron-builder
Write-Host "[3/3] Packaging Electron app for Windows..." -ForegroundColor Green
& npx electron-builder --win --dir
if ($LASTEXITCODE -ne 0) { Write-Host "Packaging failed." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Done! Packaged app is in: desktop\dist-electron\" -ForegroundColor Green
