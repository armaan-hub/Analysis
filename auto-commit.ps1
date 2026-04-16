# Auto-commit and push script for Windows
# Usage: .\auto-commit.ps1 "Your commit message" "major" | "minor"
# Example: .\auto-commit.ps1 "Fixed critical bug" "major"

param(
    [string]$CommitMessage = "Update: Code changes",
    [string]$UpdateType = "major"  # "major" or "minor"
)

# Set error action
$ErrorActionPreference = "Stop"

# Colors for output
$success = @{ ForegroundColor = "Green" }
$warning = @{ ForegroundColor = "Yellow" }
$error = @{ ForegroundColor = "Red" }
$info = @{ ForegroundColor = "Cyan" }

Write-Host "🔄 Starting automated Git workflow..." @info

# 1. Check if we're in a git repository
try {
    $repoName = git rev-parse --show-toplevel 2>$null
    Write-Host "✓ Git repository found: $repoName" @success
} catch {
    Write-Host "❌ Not a git repository. Please run from project root." @error
    exit 1
}

# 2. Get current branch
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "📍 Current branch: $branch" @info

# 3. Stage changes
Write-Host "📝 Staging changes..." @info
try {
    git add -A
    $stagedCount = (git diff --cached --name-only | Measure-Object -Line).Lines
    Write-Host "✓ Staged $stagedCount files" @success
} catch {
    Write-Host "❌ Failed to stage changes: $_" @error
    exit 1
}

# 4. Check if there are changes
$hasChanges = (git diff --cached --name-only | Measure-Object -Line).Lines -gt 0
if (-not $hasChanges) {
    Write-Host "ℹ️  No changes to commit" @warning
    exit 0
}

# 5. Format commit message with update type
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$finalMessage = "[$UpdateType] $CommitMessage - $timestamp"

# Add extra details for major updates
if ($UpdateType -eq "major") {
    $finalMessage += "`n`nAuto-committed by automated workflow`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
}

# 6. Commit changes
Write-Host "📌 Creating commit..." @info
try {
    git commit -m $finalMessage
    $commitHash = git rev-parse --short HEAD
    Write-Host "✓ Committed: $commitHash" @success
} catch {
    Write-Host "❌ Commit failed: $_" @error
    exit 1
}

# 7. Auto-push if major update
if ($UpdateType -eq "major") {
    Write-Host "📤 Major update - Auto-pushing to GitHub..." @info
    
    $pushAttempts = 3
    $pushSuccess = $false
    
    for ($i = 1; $i -le $pushAttempts; $i++) {
        try {
            git push origin $branch
            Write-Host "✅ Successfully pushed to $branch" @success
            $pushSuccess = $true
            break
        } catch {
            if ($i -lt $pushAttempts) {
                Write-Host "⚠️  Push attempt $i/$pushAttempts failed, retrying..." @warning
                Start-Sleep -Seconds 5
            } else {
                Write-Host "❌ Push failed after $pushAttempts attempts" @error
            }
        }
    }
    
    if (-not $pushSuccess) {
        Write-Host "Manual push required: git push origin $branch" @warning
        exit 1
    }
} else {
    Write-Host "ℹ️  Minor update - Skipping auto-push" @info
    Write-Host "Push manually with: git push origin $branch" @info
}

Write-Host ""
Write-Host "✅ Workflow completed successfully!" @success
Write-Host "Commit: $commitHash | Type: $UpdateType | Branch: $branch" @success
