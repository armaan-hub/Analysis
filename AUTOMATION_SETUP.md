# 🚀 Auto-Commit & Push Workflow

This automation system ensures that all major code updates are automatically committed and pushed to GitHub.

## 📋 Overview

The system detects code changes and:
- **Major Updates**: Automatically commits and pushes to GitHub
- **Minor Updates**: Commits locally (manual push available)
- **Workflow Tracking**: GitHub Actions monitors all pushes

---

## 🔧 Installation

### Step 1: Run Setup Script

```powershell
.\setup-auto-push.ps1
```

This configures:
- Git hooks for pre/post commit actions
- Git aliases for easy commands
- Auto-push settings

### Step 2: Verify Setup

```powershell
git config --list | Select-String "push\|hooks"
```

---

## 📝 Usage

### Method 1: PowerShell Script (Recommended)

**For Major Updates (auto-commit + auto-push):**
```powershell
.\auto-commit.ps1 "Feature: Added new document processing API" "major"
```

**For Minor Updates (commit only):**
```powershell
.\auto-commit.ps1 "Updated documentation" "minor"
```

### Method 2: Git Aliases

After running setup script, use shorter aliases:

**Major update:**
```powershell
git major "Feature: New RAG implementation"
```

**Minor update:**
```powershell
git minor "Fixed typo in comments"
```

### Method 3: Manual Git Commands

```powershell
# Stage changes
git add -A

# Commit with message format: [TYPE] message
git commit -m "[major] Feature: Improved LLM integration - 2026-04-16 11:15:00"

# For major updates, auto-push is triggered by post-commit hook
# OR manually push
git push origin main
```

---

## 🎯 Major vs Minor Updates

### 🔴 Major Updates (Auto-Pushed)
Automatically detected and pushed when commit message contains:
- `feature` - New functionality
- `fix` - Bug fixes
- `major` - Significant changes
- `update` - Important updates
- `improvement` - Performance/UX improvements
- `refactor` - Code structure changes
- `security` - Security patches
- `hotfix` - Critical fixes
- `critical` - Critical changes

**Example:**
```powershell
.\auto-commit.ps1 "Feature: Multi-language support added" "major"
```

### ⚪ Minor Updates (Manual Push)
For documentation, comments, formatting:

**Example:**
```powershell
.\auto-commit.ps1 "Updated README documentation" "minor"
```

---

## ⚙️ Configuration

### Git Hooks Location
- **Pre-commit**: `.git/hooks/pre-commit`
- **Post-commit**: `.git/hooks/post-commit`

### Triggered Actions

**Pre-commit Hook:**
- Validates staged changes
- Detects major code modifications
- Prevents commits with issues

**Post-commit Hook:**
- Checks commit message for keywords
- Auto-pushes if major update detected
- Retries up to 3 times if push fails

### GitHub Actions

Workflow file: `.github/workflows/auto-push.yml`

**Triggered on:**
- Backend code changes
- Frontend code changes  
- Configuration updates
- Documentation updates

**Actions performed:**
- Detects major updates
- Creates release markers
- Verifies repository integrity

---

## 📊 Automatic Detection

The system automatically detects changes in:

### Backend Changes
- `backend/main.py`
- `backend/api/**`
- `backend/core/**`
- `backend/db/**`
- `backend/requirements.txt`

### Frontend Changes
- `frontend/src/**`
- `frontend/package.json`

### Configuration Changes
- `.env.example`
- `config.py`
- `.gitignore`

### Documentation
- `README.md`
- `docs/**`

---

## 🔄 Workflow Steps

### For Major Updates:
```
1. Make code changes
   ↓
2. Run: .\auto-commit.ps1 "message" "major"
   ↓
3. Script stages all changes (git add -A)
   ↓
4. Pre-commit hook validates
   ↓
5. Commit created with:
   - [major] prefix
   - Your message
   - Timestamp
   - Copilot co-author
   ↓
6. Post-commit hook triggers
   ↓
7. Changes auto-pushed to GitHub
   ↓
8. GitHub Actions notified
   ↓
9. ✅ Complete!
```

### For Minor Updates:
```
1. Make code changes
   ↓
2. Run: .\auto-commit.ps1 "message" "minor"
   ↓
3. Script stages all changes
   ↓
4. Pre-commit hook validates
   ↓
5. Commit created with:
   - [minor] prefix
   - Your message
   - Timestamp
   ↓
6. ℹ️ Manual push required:
   git push origin main
```

---

## 🚨 Troubleshooting

### Hook Not Executing

**Problem:** Auto-push not working after commit

**Solution:**
```powershell
# Re-enable hooks
git config core.hooksPath .git/hooks

# Make hooks executable (Unix)
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-commit
```

### Push Fails Silently

**Problem:** Commit created but not pushed

**Reason:** Network issues or auth problems

**Solution:**
```powershell
# Manual retry
git push origin main

# Check logs
git log -1
git status
```

### Hook Requires Manual Input

**Problem:** Script hangs during commit

**Solution:**
```powershell
# Cancel (Ctrl+C) and try again with verbose output
$VerbosePreference = "Continue"
.\auto-commit.ps1 -Verbose
```

---

## 📈 Monitoring

### View Recent Commits
```powershell
git status-check
# Shows last 10 commits with graph
```

### View Auto-Push History
```powershell
git log --oneline --grep="auto-commit"
```

### Check Hook Status
```powershell
git config core.hooksPath
git config alias.major
git config alias.minor
```

---

## 🔐 Security Notes

- ✅ Uses existing GitHub authentication
- ✅ No passwords stored in scripts
- ✅ Commits include Copilot co-author trailer
- ✅ All changes tracked in git history
- ✅ Retries handle temporary network issues

---

## 💡 Best Practices

1. **Always verify changes before commit**
   ```powershell
   git diff  # Review changes
   git add -A
   git diff --cached  # Review staged changes
   ```

2. **Use descriptive commit messages**
   ```powershell
   .\auto-commit.ps1 "Feature: Implemented RAG-based document analysis" "major"
   ```

3. **For multiple related changes**
   - Make individual commits for each logical change
   - Use appropriate update type for each

4. **Team coordination**
   - Communicate major updates to team
   - Use descriptive messages
   - Include context in commit body

---

## 🎓 Examples

### Example 1: New Backend Feature
```powershell
.\auto-commit.ps1 "Feature: Added multi-LLM provider switching" "major"
```
**Result:** Auto-committed + auto-pushed + GitHub notified

### Example 2: Bug Fix
```powershell
.\auto-commit.ps1 "Fix: Resolved memory leak in RAG engine" "major"
```
**Result:** Auto-committed + auto-pushed + GitHub notified

### Example 3: Documentation Update
```powershell
.\auto-commit.ps1 "Updated API documentation" "minor"
```
**Result:** Committed locally, manual push required

### Example 4: Security Patch
```powershell
.\auto-commit.ps1 "Security: Updated API key validation" "major"
```
**Result:** Auto-committed + auto-pushed immediately (critical)

---

## 📚 Additional Resources

- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Setup script ran successfully
- [ ] Git aliases configured (`git config --list | grep major`)
- [ ] Auto-commit script is executable (`Get-Item .\auto-commit.ps1 | Select ExecutionPolicy`)
- [ ] GitHub Actions workflow created (`.github/workflows/auto-push.yml`)
- [ ] Pre-commit hook configured
- [ ] Post-commit hook configured
- [ ] Test run successful (`.\auto-commit.ps1 "Test commit" "minor"`)

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review git logs: `git log --oneline -20`
3. Run diagnostic: `git status`, `git diff`

---

**Version**: 1.0.0  
**Last Updated**: April 16, 2026  
**Author**: Armaan / Copilot
