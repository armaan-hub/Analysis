param(
    [switch]$RecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$desktopDir = Join-Path $projectRoot "desktop"
$venvDir = Join-Path $backendDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "Installing project dependencies..." -ForegroundColor Cyan

Require-Command python
Require-Command npm

if ($RecreateVenv -and (Test-Path $venvDir)) {
    Write-Host "Recreating backend virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $backendDir
    try {
        python -m venv venv
    } finally {
        Pop-Location
    }
}

Write-Host "Installing backend Python packages..." -ForegroundColor Yellow
Push-Location $backendDir
try {
    & $venvPython -m ensurepip --upgrade
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -r requirements.txt
} finally {
    Pop-Location
}

Write-Host "Installing frontend Node packages..." -ForegroundColor Yellow
Push-Location $frontendDir
try {
    if (Test-Path (Join-Path $frontendDir "package-lock.json")) {
        npm ci
    } else {
        npm install
    }
} finally {
    Pop-Location
}

if (Test-Path (Join-Path $desktopDir "package.json")) {
    Write-Host "Installing desktop Node packages..." -ForegroundColor Yellow
    Push-Location $desktopDir
    try {
        if (Test-Path (Join-Path $desktopDir "package-lock.json")) {
            npm ci
        } else {
            npm install
        }
    } finally {
        Pop-Location
    }
}

Write-Host "All dependencies installed successfully." -ForegroundColor Green
Write-Host "Backend Python: $venvPython"
