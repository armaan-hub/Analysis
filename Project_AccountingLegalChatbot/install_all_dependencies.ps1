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

# ── Prerequisite version gates ────────────────────────────────────
Require-Command python
$pyVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pyVersion -lt [version]"3.11") {
    throw "Python 3.11+ required (found $pyVersion). Please upgrade Python."
}
Write-Host "  Python $pyVersion OK" -ForegroundColor Green

Require-Command node
$nodeVersion = (node --version).TrimStart('v')
if ([version]$nodeVersion -lt [version]"20.0.0") {
    throw "Node.js 20+ required (found $nodeVersion). React 19 / Vite 6 require Node 20+."
}
Write-Host "  Node $nodeVersion OK" -ForegroundColor Green

Require-Command npm

# ── Optional prerequisite warnings ───────────────────────────────
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
    Write-Warning "tesseract not found in PATH — OCR for scanned Arabic PDFs will not work.`n  Install: winget install UB-Mannheim.TesseractOCR"
}
if (-not (Get-Command pdftoppm -ErrorAction SilentlyContinue)) {
    Write-Warning "poppler (pdftoppm) not found in PATH — pdf2image will not work.`n  Download: https://github.com/oschwartz10612/poppler-windows/releases"
}

if ($RecreateVenv -and (Test-Path $venvDir)) {
    Write-Host "Recreating backend virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    # Use the full $venvDir path so the venv always lands in backend/venv/ regardless of CWD
    python -m venv "$venvDir"
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

# Download spaCy English model (required for NLP features)
Write-Host "Downloading spaCy language model (en_core_web_sm)..." -ForegroundColor Yellow
& $venvPython -m spacy download en_core_web_sm

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
