param(
    [switch]$RecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = $PSScriptRoot
$projectRoot = Join-Path $workspaceRoot "Project_AccountingLegalChatbot"
$backendDir = Join-Path $projectRoot "backend"
$venvDir = Join-Path $backendDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $backendDir "requirements.txt"

if (-not (Test-Path $backendDir)) {
    throw "Backend directory not found: $backendDir"
}
if (-not (Test-Path $requirementsFile)) {
    throw "requirements.txt not found: $requirementsFile"
}

function Get-PythonBootstrapCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    return $null
}

function Refresh-ProcessPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

$pythonBootstrap = Get-PythonBootstrapCommand

if (-not $pythonBootstrap) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Python not found. Attempting install via winget..." -ForegroundColor Yellow
        winget install --id Python.Python.3.12 -e --source winget --silent --accept-package-agreements --accept-source-agreements
        Refresh-ProcessPath
        $pythonBootstrap = Get-PythonBootstrapCommand
    }
}

if (-not $pythonBootstrap) {
    throw "Python is not available and auto-install failed. Install Python 3.11+ and rerun this script."
}

if ($RecreateVenv -and (Test-Path $venvDir)) {
    Write-Host "Recreating virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Cyan
    Push-Location $backendDir
    try {
        if ($pythonBootstrap -eq "py") {
            py -3 -m venv venv
        } else {
            python -m venv venv
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Installing backend Python requirements..." -ForegroundColor Cyan
& $venvPython -m ensurepip --upgrade
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r $requirementsFile

Write-Host "Python environment is ready." -ForegroundColor Green
Write-Host "Venv path: $venvDir"
Write-Host "Python path: $venvPython"
