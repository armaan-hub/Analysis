# run_project.ps1
# Starts backend (uvicorn) + frontend (vite dev) with auto-restart on crash.
# Press Ctrl+C to stop both cleanly.

$ErrorActionPreference = "Continue"

$ROOT          = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND       = Join-Path $ROOT "backend"
$FRONTEND      = Join-Path $ROOT "frontend"
$PYTHON        = Join-Path $BACKEND "venv\Scripts\python.exe"   # use directly — avoids Activate.ps1 issues in jobs
$BACKEND_LOG   = Join-Path $ROOT "backend_server.log"
$FRONTEND_LOG  = Join-Path $ROOT "frontend_server.log"
$LAUNCHER_LOG  = Join-Path $ROOT "run_project.log"

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LAUNCHER_LOG -Value "[$ts] $Message" -Encoding UTF8 -ErrorAction SilentlyContinue
}

Write-Log ""
Write-Log "============================================" Cyan
Write-Log "  Accounting & Legal Chatbot - Launcher" Cyan
Write-Log "============================================" Cyan
Write-Log ""

# ── Verify paths ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PYTHON)) {
    Write-Log "[ERROR] Python venv not found at: $PYTHON" Red
    Write-Log "        Run install_all_dependencies.ps1 first." Yellow
    exit 1
}
if (-not (Test-Path (Join-Path $FRONTEND "package.json"))) {
    Write-Log "[ERROR] Frontend package.json not found at: $FRONTEND" Red
    exit 1
}

Write-Log "  Backend  : http://localhost:8000" White
Write-Log "  Frontend : http://localhost:5173" White
Write-Log "  API Docs : http://localhost:8000/docs" White
Write-Log "  Logs     : backend_server.log | frontend_server.log" White
Write-Log "  Press Ctrl+C to stop both services." Yellow
Write-Log ""

# ── Job factory functions ─────────────────────────────────────────────────────
function New-BackendJob {
    param($backendPath, $pythonExe)
    return Start-Job -ScriptBlock {
        param($bp, $py)
        Set-Location $bp
        $env:PYTHONUTF8 = "1"   # prevents UnicodeEncodeError on Windows cp1252 terminals
        & $py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload 2>&1
    } -ArgumentList $backendPath, $pythonExe
}

function New-FrontendJob {
    param($frontendPath)
    return Start-Job -ScriptBlock {
        param($fp)
        Set-Location $fp
        & npm run dev 2>&1
    } -ArgumentList $frontendPath
}

# ── Restart policy ────────────────────────────────────────────────────────────
$RESTART_DELAY    = 3    # seconds to wait before restarting
$MAX_CONSEC_FAILS = 5    # stop after this many back-to-back crashes
$STABLE_THRESHOLD = 30   # seconds of uptime that resets the crash counter

# ── Initial launch ────────────────────────────────────────────────────────────
Write-Log "[1/2] Starting backend ..."  Green
$backendJob    = New-BackendJob  $BACKEND $PYTHON
$backendFails  = 0
$backendStart  = Get-Date

Write-Log "[2/2] Starting frontend ..." Green
$frontendJob   = New-FrontendJob $FRONTEND
$frontendFails = 0
$frontendStart = Get-Date

Write-Log ""

# ── Main loop ─────────────────────────────────────────────────────────────────
try {
    while ($true) {

        # Forward backend output
        $out = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        if ($out) {
            $out | ForEach-Object {
                Write-Host "[backend]  $_" -ForegroundColor DarkCyan
                Add-Content -Path $BACKEND_LOG -Value $_ -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }

        # Forward frontend output
        $out = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
        if ($out) {
            $out | ForEach-Object {
                Write-Host "[frontend] $_" -ForegroundColor DarkGreen
                Add-Content -Path $FRONTEND_LOG -Value $_ -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }

        # ── Auto-restart backend if stopped ──────────────────────────────────
        if ($backendJob.State -in "Completed", "Failed", "Stopped") {
            $uptime = (Get-Date) - $backendStart
            if ($uptime.TotalSeconds -ge $STABLE_THRESHOLD) { $backendFails = 0 }  # was stable — reset counter
            $backendFails++
            if ($backendFails -gt $MAX_CONSEC_FAILS) {
                Write-Log "[ERROR] Backend crashed $MAX_CONSEC_FAILS times in a row. Fix the error above and re-run the script." Red
                break
            }
            $uptimeSec = [int]$uptime.TotalSeconds
            Write-Log "[RESTART $backendFails/$MAX_CONSEC_FAILS] Backend stopped (uptime: ${uptimeSec}s). Restarting in ${RESTART_DELAY}s..." Yellow
            Start-Sleep -Seconds $RESTART_DELAY
            Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
            $backendJob   = New-BackendJob $BACKEND $PYTHON
            $backendStart = Get-Date
            Write-Log "[OK] Backend restarted." Green
        }

        # ── Auto-restart frontend if stopped ─────────────────────────────────
        if ($frontendJob.State -in "Completed", "Failed", "Stopped") {
            $uptime = (Get-Date) - $frontendStart
            if ($uptime.TotalSeconds -ge $STABLE_THRESHOLD) { $frontendFails = 0 }
            $frontendFails++
            if ($frontendFails -gt $MAX_CONSEC_FAILS) {
                Write-Log "[ERROR] Frontend crashed $MAX_CONSEC_FAILS times in a row. Fix the error above and re-run the script." Red
                break
            }
            $uptimeSec = [int]$uptime.TotalSeconds
            Write-Log "[RESTART $frontendFails/$MAX_CONSEC_FAILS] Frontend stopped (uptime: ${uptimeSec}s). Restarting in ${RESTART_DELAY}s..." Yellow
            Start-Sleep -Seconds $RESTART_DELAY
            Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
            $frontendJob   = New-FrontendJob $FRONTEND
            $frontendStart = Get-Date
            Write-Log "[OK] Frontend restarted." Green
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    # ── Clean shutdown on Ctrl+C ─────────────────────────────────────────────
    Write-Log ""
    Write-Log "Shutting down services..." Yellow
    if ($backendJob) {
        Stop-Job  -Job $backendJob  -ErrorAction SilentlyContinue
        Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
        Write-Log "  [OK] Backend stopped." DarkGray
    }
    if ($frontendJob) {
        Stop-Job  -Job $frontendJob  -ErrorAction SilentlyContinue
        Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
        Write-Log "  [OK] Frontend stopped." DarkGray
    }
    Write-Log "Done." Green
}
