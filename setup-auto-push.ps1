# Setup Auto-Push Workflow
# This script configures Git hooks and automation for auto-commit/push

Write-Host "🔧 Setting up Auto-Push Workflow..." -ForegroundColor Cyan

# 1. Configure Git hooks
Write-Host "`n📝 Configuring Git hooks..." -ForegroundColor Yellow

# Enable git hooks directory
git config core.hooksPath .git/hooks

Write-Host "✓ Git hooks enabled" -ForegroundColor Green

# 2. Create helpful alias commands
Write-Host "`n⌨️  Setting up Git aliases..." -ForegroundColor Yellow

# Alias for major update commit + push
git config alias.major '!powershell -NoProfile -Command "& ''./auto-commit.ps1'' @args major"'

# Alias for minor update commit (no push)
git config alias.minor '!powershell -NoProfile -Command "& ''./auto-commit.ps1'' @args minor"'

# Alias for checking repository status
git config alias.status-check 'log --oneline -10 --graph --decorate'

Write-Host "✓ Git aliases created:" -ForegroundColor Green
Write-Host "  - git major 'message'     (auto-commit + push)" -ForegroundColor Gray
Write-Host "  - git minor 'message'     (commit only)" -ForegroundColor Gray
Write-Host "  - git status-check        (view recent commits)" -ForegroundColor Gray

# 3. Configure auto-push settings
Write-Host "`n⚙️  Configuring auto-push settings..." -ForegroundColor Yellow

# Set push default behavior
git config push.default current

# Enable auto-squash for interactive rebase
git config rebase.autosquash true

# Set fast-forward only for pull
git config pull.ff only

Write-Host "✓ Git settings configured" -ForegroundColor Green

# 4. Create helper scripts directory
$scriptsDir = "./.automation"
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir | Out-Null
    Write-Host "✓ Created automation scripts directory" -ForegroundColor Green
}

# 5. Display configuration summary
Write-Host "`n📊 Auto-Push Workflow Configuration Summary:" -ForegroundColor Cyan
Write-Host "============================================"

Write-Host "`n🎯 How to use:" -ForegroundColor Yellow
Write-Host "1. Major code update (auto-commit + push):"
Write-Host "   .\auto-commit.ps1 'Your message' 'major'" -ForegroundColor Green
Write-Host "   OR use alias: git major 'Your message'" -ForegroundColor Green

Write-Host "`n2. Minor code update (commit only, manual push):"
Write-Host "   .\auto-commit.ps1 'Your message' 'minor'" -ForegroundColor Green
Write-Host "   OR use alias: git minor 'Your message'" -ForegroundColor Green

Write-Host "`n3. View recent commits:"
Write-Host "   git status-check" -ForegroundColor Green

Write-Host "`n📌 What triggers auto-push?" -ForegroundColor Yellow
Write-Host "  - Commit messages with: feature, fix, major, update, improvement"
Write-Host "  - Commit messages with: refactor, security, hotfix, critical"

Write-Host "`n🔄 Automation Workflow:" -ForegroundColor Yellow
Write-Host "  1. Your code changes (any file)" -ForegroundColor Gray
Write-Host "  2. Run: .\auto-commit.ps1 'message' 'major'" -ForegroundColor Gray
Write-Host "  3. Changes staged automatically" -ForegroundColor Gray
Write-Host "  4. Commit created with timestamp" -ForegroundColor Gray
Write-Host "  5. Auto-pushed to GitHub (if major)" -ForegroundColor Gray
Write-Host "  6. GitHub Actions notified" -ForegroundColor Gray

Write-Host "`n✅ Setup completed successfully!" -ForegroundColor Green
Write-Host "`nYou can now use auto-commit/push workflow for major updates." -ForegroundColor Cyan
