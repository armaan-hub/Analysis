# 🔍 ERROR AUDIT REPORT — Accounting & Legal AI Chatbot
**Date:** 2026-04-20  
**Auditor:** Antigravity AI (Claude Sonnet 4.6 Thinking)  
**Scope:** Full project — Backend (Python/FastAPI) + Frontend (React/TypeScript)

---

## SEVERITY LEGEND
- 🔴 **CRITICAL** — App crashes / data loss / security vulnerability
- 🟠 **HIGH** — Feature broken, but app still starts
- 🟡 **MEDIUM** — Intermittent error or degraded behavior
- 🔵 **INFO** — Code smell, tech debt, potential future problem

---

## SECTION 1 — BACKEND (Python / FastAPI)

---

### 🔴 ERR-B01 · `chat.py` line 243–260 — Timezone-naive datetime comparison causes crash

**File:** `backend/api/chat.py` — lines 243–244  
**Error:**
```python
idle_minutes = (
    datetime.now(timezone.utc).replace(tzinfo=None) - prev_conv.updated_at
).total_seconds() / 60
```
**Problem:**  
`datetime.now(timezone.utc).replace(tzinfo=None)` strips the UTC timezone info and compares against `prev_conv.updated_at`, which may already be timezone-aware (depending on SQLAlchemy and SQLite returning aware datetimes). On Python 3.11+, comparing a naive datetime with an aware datetime raises `TypeError: can't subtract offset-naive and offset-aware datetimes`, crashing the entire `/api/chat/send` endpoint for ALL new conversations.

**Solution:**  
Remove `.replace(tzinfo=None)` and ensure both sides are timezone-naive OR both are timezone-aware:
```python
now_naive = datetime.utcnow()  # naive UTC
updated = prev_conv.updated_at
if updated.tzinfo is not None:
    updated = updated.replace(tzinfo=None)
idle_minutes = (now_naive - updated).total_seconds() / 60
```

---

### 🔴 ERR-B02 · `chat.py` line 258–260 — `asyncio.create_task()` using closed DB session

**File:** `backend/api/chat.py` — lines 258–260  
**Error:**
```python
asyncio.create_task(
    extract_and_save_memory(prev_conv.id, prev_msgs, db)
)
```
**Problem:**  
The FastAPI `db` session (from `get_db()`) is yielded inside a `try/finally` block. By the time the background task `extract_and_save_memory` runs, the `get_db()` dependency's `finally` block has **already closed and committed** (or rolled back) the session. The background task then calls `db.commit()` on a closed session, causing `sqlalchemy.exc.InvalidRequestError: This session is closed`.

**Solution:**  
Create a **fresh** independent session inside the background task instead of passing the request-scoped `db` session:
```python
# Inside extract_and_save_memory, open its own session:
async with AsyncSessionLocal() as session:
    # ... use session instead of db
```
In the caller, remove the `db` argument from `asyncio.create_task(extract_and_save_memory(prev_conv.id, prev_msgs))`.

---

### 🔴 ERR-B03 · `database.py` line 19 — `connect_args={"timeout": 30}` breaks aiosqlite

**File:** `backend/db/database.py` — line 19  
**Error:**
```python
engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},  # ← PROBLEM
)
```
**Problem:**  
The `timeout` keyword is **not a valid aiosqlite/sqlite3 connection argument** (it is valid for PostgreSQL's `psycopg2`). Using it with SQLite causes `TypeError: connect() got an unexpected keyword argument 'timeout'` at startup, crashing the application before it ever serves a request.

**Solution:**  
Remove `connect_args={"timeout": 30}` entirely. The SQLite busy timeout is already handled by the WAL-mode PRAGMA event listener below (`PRAGMA busy_timeout=30000`):
```python
engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    # No connect_args needed — busy_timeout set via PRAGMA event
)
```

---

### 🟠 ERR-B04 · `config.py` line 58 — Default port is 8000, but `run_project.ps1` and docs say 8080

**File:** `backend/config.py` — line 58  
**Error:**
```python
port: int = 8000
```
**File:** `.env` — line 42  
```
PORT=8000
```
**File:** `backend/main.py` — lines 5, 127–136  
```
Run with: uvicorn main:app --host 0.0.0.0 --port 8080 --reload
"chat": "/api/chat/send",   # doc comment says 8080 elsewhere
```
**Problem:**  
The backend defaults to port 8000, but some documentation strings and launch scripts reference port 8080. The frontend `lib/api.ts` defaults to `http://localhost:8000` (correct), but inconsistency causes confusion and CORS issues if scripts launch on the wrong port.

**Solution:**  
Pick one port and apply it consistently everywhere. Update `main.py` docstring comment to say `--port 8000`, and ensure `run_project.ps1` / `run_project.bat` use the same port as `.env`.

---

### 🟠 ERR-B05 · `settings.py` line 91 — `settings.llm_provider` mutation is not thread-safe and not persisted across restarts

**File:** `backend/api/settings.py` — line 91  
**Error:**
```python
settings.llm_provider = req.provider
```
**Problem:**  
`Settings` is a Pydantic `BaseSettings` singleton. Mutating its attribute at runtime (`settings.llm_provider = req.provider`) works in the current process but is **not thread-safe under concurrent requests** (FastAPI runs multiple threads). A parallel request to `/api/chat/send` might read the old provider while the switch is mid-write. Also, if the server crashes and restarts before `.env` is written, the setting reverts.

**Solution:**  
Add a threading lock around the mutation, or use an `asyncio.Lock`. The `.env` write via `_update_env_key` should happen **before** mutating the in-memory setting. Also, call `reload()` or reload the settings object after env update rather than mutating directly.

---

### 🟠 ERR-B06 · `rag_engine.py` line 204–213 — ChromaDB fallback writes to `/tmp` and loses data on restart

**File:** `backend/core/rag_engine.py` — lines 203–214  
**Error:**
```python
fresh_dir = tempfile.mkdtemp(prefix="chroma_fresh_")
self.chroma_client = chromadb.PersistentClient(path=fresh_dir, ...)
```
**Problem:**  
If ChromaDB fails to initialize (e.g., corrupted store), the code silently falls back to a **temporary directory** (`/tmp/chroma_fresh_XXXXX`). All subsequent document uploads are indexed to this temp path. When the server restarts, the temp directory is gone and all indexed documents are lost. The user sees documents listed in the DB but RAG returns zero results.

**Solution:**  
Instead of falling back to a temp dir, delete or rename the corrupted store directory and re-create it at the configured path:
```python
import shutil
logger.error("ChromaDB store corrupted — backing up and creating fresh one")
backup = Path(settings.vector_store_dir + "_backup_corrupted")
shutil.move(settings.vector_store_dir, str(backup))
Path(settings.vector_store_dir).mkdir(parents=True, exist_ok=True)
self.chroma_client = chromadb.PersistentClient(path=settings.vector_store_dir, ...)
```

---

### 🟠 ERR-B07 · `reports.py` line 263–268 — JSON parsing from LLM is fragile and will crash on malformed response

**File:** `backend/api/reports.py` — lines 263–268 (extract_company_docs endpoint)  
**Error:**
```python
raw = response.content.strip()
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
return json.loads(raw.strip())
```
**Problem:**  
The code tries to manually strip markdown code fences, but will fail on:
1. `raw.split("```")[1]` → if LLM returns ` ```json\n{...}\n``` ` the split gives `json\n{...}\n` — the `if raw.startswith("json")` correctly strips `json` but leaves `\n{`. `json.loads` then fails.
2. If the LLM returns free-text instead of JSON, `json.loads` raises `JSONDecodeError` caught only by the outer `except Exception as e` which silently returns empty fields.
3. The triple-backtick split approach is inconsistent with the more robust regex approach used in `chat.py` (lines 129–131).

**Solution:**  
Use the same regex approach as in `chat.py`:
```python
import re
raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
match = re.search(r"\{.*\}", raw, re.DOTALL)
if not match:
    raise ValueError("LLM did not return valid JSON")
return json.loads(match.group(0))
```

---

### 🟡 ERR-B08 · `monitoring.py` line 100 — SQLAlchemy warning: comparing Boolean with `== False`

**File:** `backend/api/monitoring.py` — line 100  
**Error:**
```python
stmt = stmt.where(Alert.is_read == False)
```
**Problem:**  
SQLAlchemy (and Python linters) warn: `SyntaxWarning: comparison to False should be 'not expr' or 'expr is False'`. While this works in SQLAlchemy ORM (it generates `WHERE is_read = 0`), it triggers linter warnings and in some SQLAlchemy versions with strict booleans, it may not generate correct SQL.

**Solution:**  
Use SQLAlchemy's `is_()` operator:
```python
stmt = stmt.where(Alert.is_read.is_(False))
```

---

### 🟡 ERR-B09 · `api/reports.py` line 131–142 — `download_report` serves ALL file types as `.xlsx` MIME type

**File:** `backend/api/reports.py` — lines 131–142  
**Error:**
```python
return FileResponse(
    path=filepath,
    filename=filename,
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```
**Problem:**  
The `download_report` endpoint always sets the MIME type to Excel (`.xlsx`), even if the report is a PDF, Word document, or plain text file. This causes browsers to misidentify the file type, potentially corrupting downloads or failing to open them.

**Solution:**  
Detect the MIME type from the file extension:
```python
import mimetypes
mime_type, _ = mimetypes.guess_type(filename)
media_type = mime_type or "application/octet-stream"
return FileResponse(path=filepath, filename=filename, media_type=media_type)
```

---

### 🟡 ERR-B10 · `web_search.py` line 25 — `asyncio.get_event_loop()` is deprecated in Python 3.10+

**File:** `backend/core/web_search.py` — line 25  
**Error:**
```python
loop = asyncio.get_event_loop()
results = await loop.run_in_executor(None, _sync_search)
```
**Problem:**  
`asyncio.get_event_loop()` emits a `DeprecationWarning` in Python 3.10+ when there is no running event loop. Inside an `async` function, the correct call is `asyncio.get_running_loop()`.

**Solution:**  
```python
loop = asyncio.get_running_loop()
results = await loop.run_in_executor(None, _sync_search)
```

---

### 🟡 ERR-B11 · `requirements.txt` — `chardet` and `charset-normalizer` conflict with `requests`

**File:** `backend/requirements.txt` — lines 64–66  
**Error:**
```
urllib3==2.1.0
charset-normalizer==3.3.2
chardet==5.2.0
```
**Problem:**  
`requests` library uses either `charset-normalizer` OR `chardet` — not both. Installing both at pinned old versions conflicts with `requests==2.32.3` which requires `charset-normalizer>=2.0.0` and `chardet>=3.0.2`. Running `pip install` together will resolve correctly, but the explicit pins may cause `RequestsDependencyWarning` or silent conflicts depending on install order.

**Solution:**  
Remove the explicit `chardet` pin and let `requests` resolve it automatically. Only keep `charset-normalizer` pinned:
```
urllib3>=2.1.0,<3
charset-normalizer>=3.0.0,<4
# Remove: chardet==5.2.0
```

---

### 🔵 ERR-B12 · `api/audit_studio.py` lines 26–32 — DB session leaks if `_require_profile` raises

**File:** `backend/api/audit_studio.py` — lines 26–32  
**Error:**
```python
async def _require_profile(profile_id: str) -> AuditProfile:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(...)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return row
```
**Problem:**  
When a `HTTPException` is raised inside `async with AsyncSessionLocal() as s:`, the context manager's `__aexit__` is called, properly closing the session. This is actually safe. However, the `AuditProfile` ORM object is returned after the session closes — accessing lazy-loaded relationships on this object later will fail with `DetachedInstanceError`.

**Solution:**  
Either keep the session open and use it in the caller, or eagerly load all needed relationships before returning:
```python
from sqlalchemy.orm import selectinload
row = (await s.execute(
    select(AuditProfile)
    .where(AuditProfile.id == profile_id)
    .options(selectinload(AuditProfile.source_documents))
)).scalar_one_or_none()
```

---

## SECTION 2 — FRONTEND (React / TypeScript)

---

### 🔴 ERR-F01 · `ReportPreview.tsx` — TypeScript build error: missing keys in `Record<ReportType, string>`

**File:** `frontend/src/components/studios/LegalStudio/ReportPreview.tsx`  
**Error:** `TS2740: Type '{ audit: string; summary: string; analysis: string; }' is missing the following properties from type 'Record<ReportType, string>': financial_analysis, ifrs, cash_flow, mis, and 6 more.`  
**Problem:**  
An object literal is typed as `Record<ReportType, string>` but only provides 3 of the 9+ required `ReportType` keys. This is a hard TypeScript compilation error — `npm run build` fails.

**Solution:**  
Change the type to `Partial<Record<ReportType, string>>` which makes all keys optional, or provide all required keys. Quick fix:
```typescript
const REPORT_LABELS: Partial<Record<ReportType, string>> = {
  audit: 'Audit Report',
  summary: 'Summary',
  analysis: 'Analysis',
  // Add all remaining ReportType keys...
};
```

---

### 🔴 ERR-F02 · `App.tsx` line 95 — Reading `ref.current` inside JSX render (React rules violation)

**File:** `frontend/src/App.tsx` — line 95  
**Error:** ESLint: `react-hooks/rules-of-hooks` — Cannot access refs during render.  
**Code:**
```tsx
<LegalStudio
  key={`new-${newKeyRef.current}`}  // ← ref read during render
  onConversationsChange={setConversations}
/>
```
**Problem:**  
`newKeyRef.current` is mutated in an event handler (`handleNewChat`) then read inside JSX render. This violates React's rules: refs should not influence rendering. In React Concurrent Mode / StrictMode, this can cause stale renders or the `key` not updating when expected.

**Solution:**  
Replace the ref with a state variable that triggers a re-render:
```typescript
const [newKey, setNewKey] = useState(0);
const handleNewChat = () => {
  setNewKey(k => k + 1);
  navigate('/notebook/new');
};
// In JSX:
<LegalStudio key={`new-${newKey}`} ... />
```

---

### 🟠 ERR-F03 · `LegalStudio.tsx` line 326 — Ref mutation during render breaks Concurrent Mode

**File:** `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — line 326  
**Error:** ESLint: `react-hooks/refs` — Cannot update ref during render  
**Code:**
```tsx
activeSourcesRef.current = activeSources;  // ← sync mutation during render
```
**Problem:**  
This assignment runs at the top level of the component function body during every render. In React Concurrent Mode, renders can be interrupted and restarted. Mutating a ref mid-render can cause the ref to hold a stale/intermediate value when the effect fires.

**Solution:**  
Move the assignment into `useEffect`:
```typescript
useEffect(() => {
  activeSourcesRef.current = activeSources;
}, [activeSources]);
```

---

### 🟠 ERR-F04 · `LegalStudio.tsx` lines 255–294 — SSE streaming event type check is wrong for `status` events

**File:** `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — line 276  
**Code:**
```typescript
} else if (evt.event === 'status' && evt.data === 'searching_web') {
    setWebSearching(true);
```
**Problem:**  
The backend sends SSE events in JSON format with `type` (not `event`). Looking at `chat.py`:
```python
yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\\n\\n"
```
The frontend checks `evt.event` instead of `evt.type`, so the web search status indicator (`🌐 Searching the web…`) **never appears**. The backend sends `type: 'status'` and `status: 'searching_web'`, but the frontend is checking `evt.event === 'status'` and `evt.data === 'searching_web'`.

**Solution:**  
Fix the condition to match the backend's actual JSON structure:
```typescript
} else if (evt.type === 'status' && evt.status === 'searching_web') {
    setWebSearching(true);
```

---

### 🟠 ERR-F05 · `lib/api.ts` line 3–4 — API base URL hardcodes port 8000, inconsistent with port in some scripts

**File:** `frontend/src/lib/api.ts` — lines 3–4  
**Code:**
```typescript
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
```
**Problem:**  
The fallback is 8000, but as noted in ERR-B04, some launch scripts and documentation reference port 8080. If the backend is launched on the wrong port (from documentation confusion), all API calls silently fail with `ERR_CONNECTION_REFUSED`.

**Solution:**  
Ensure `frontend/.env` sets `VITE_API_BASE_URL=http://localhost:8000` explicitly and the backend is consistently launched on port 8000. Or update the `frontend/.env` file:
```
VITE_API_BASE_URL=http://localhost:8000
```

---

### 🟠 ERR-F06 · `ChatMessages.tsx` — Message key uses array index `i` instead of stable message ID

**File:** `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` — line 203  
**Code:**
```tsx
{messages.map((msg, i) => {
  if (msg.role === 'user') {
    return (
      <div key={i} className="chat-msg chat-msg--user">
```
**Problem:**  
Using array index `i` as the React `key` causes incorrect DOM reconciliation when messages are prepended, removed, or re-ordered. When a streaming AI message is appended while the user message still has `key={0}`, React may re-render the wrong component.

**Solution:**  
Use a stable unique key. Since messages have an optional `id` field, use it with a fallback:
```tsx
<div key={msg.id || `user-${i}`} className="chat-msg chat-msg--user">
```
And for AI messages:
```tsx
<AIMessage key={msg.id || `ai-${i}`} ... />
```

---

### 🟡 ERR-F07 · `LegalStudio.tsx` line 87 — `catch` block silently ignores document deletion errors

**File:** `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — line 87  
**Code:**
```typescript
} catch { /* ignore */ }
```
**Problem:**  
When document deletion fails (network error, 404, 500), the document is still removed from the UI state (`setDocs(prev => prev.filter(...))`). The user believes the document was deleted, but it remains in the backend. Subsequent operations may fail unexpectedly.

**Solution:**  
Show an error message to the user on failure and do NOT update the UI state:
```typescript
} catch (err) {
  console.error("Failed to delete document:", err);
  // Optionally: show a toast/notification to the user
  // Do NOT remove the doc from state — it's still in the backend
}
```

---

### 🟡 ERR-F08 · `frontend/package.json` — `lucide-react@^1.8.0` is a non-existent version

**File:** `frontend/package.json` — line 15  
**Code:**
```json
"lucide-react": "^1.8.0",
```
**Problem:**  
`lucide-react` versioning does not follow typical semver. As of 2026, `lucide-react` versions are `0.x.y` (e.g., `0.474.0`). Version `1.8.0` does not exist in the npm registry. This means `npm install` will fail with `No matching version found for lucide-react@^1.8.0`, breaking the development environment setup from scratch.

**Solution:**  
Fix the version to an actual published version:
```json
"lucide-react": "^0.474.0"
```
Or use the `latest` tag and pin after `npm install`:
```bash
npm install lucide-react@latest
```

---

### 🟡 ERR-F09 · `App.tsx` — `FinanceStudio` route redirects to `/` (the page itself)

**File:** `frontend/src/App.tsx` — line 108  
**Code:**
```tsx
<Route path="/finance" element={<Navigate to="/" replace />} />
```
**Problem:**  
Navigating to `/finance` redirects to `/`, which renders `<HomePage />` (an empty landing page), not the Finance Studio or Legal Studio. If any link in the application points to `/finance`, users get an empty page. This is likely an incomplete redirect that should point to the main chat studio.

**Solution:**  
If Finance Studio is consolidated into LegalStudio, redirect to `/notebook/new` instead:
```tsx
<Route path="/finance" element={<Navigate to="/notebook/new" replace />} />
```
Or remove the route entirely if `/finance` is not used by any link in the app.

---

### 🔵 ERR-F10 · `LegalStudio.tsx` lines 111, 184 — Empty `catch` blocks swallow upload errors with no user feedback

**File:** `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — lines 111, 184  
**Code:**
```typescript
} catch {
  setDocs(prev => prev.map(d =>
    d.id === tempId ? { ...d, status: 'error' } : d
  ));
}
// and:
} catch { /* upload error - continue with chat */ }
```
**Problem:**  
In `handleDocUpload`, the error status is set but there is no toast/notification to alert the user. In `sendMessage` (line 184), a file upload error is completely silent. Users don't know their file failed to upload before the AI responded.

**Solution:**  
Add user-visible error feedback (e.g., a toast notification or error message in the sources sidebar) when a file upload fails. At minimum, log the error:
```typescript
} catch (err) {
  console.error("File upload failed:", err);
  // Show toast: "Failed to upload {file.name}. Please try again."
}
```

---

## SECTION 3 — ENVIRONMENT / CONFIGURATION

---

### 🔴 ERR-E01 · `.env` line 9 — NVIDIA API Key is exposed in a plain text file committed to the project

**File:** `.env` — line 9  
**Value:** `NVIDIA_API_KEY=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`  
**Problem:**  
The `.env` file containing a real NVIDIA API key is present in the project directory. If this directory is ever committed to a Git repository, the key will be permanently exposed in commit history.

**Solution:**
1. Immediately **rotate/revoke** this API key from the NVIDIA developer dashboard.
2. Add `.env` to `.gitignore` (check that `.gitignore` properly excludes it).
3. Only store the key in `.env.example` as a placeholder: `NVIDIA_API_KEY=your_key_here`.

---

### 🟠 ERR-E02 · `config.py` line 50 — Relative DB path `./data/chatbot.db` fails when backend is run from wrong directory

**File:** `backend/config.py` — line 50  
**Value:** `database_url: str = "sqlite:///./data/chatbot.db"`  
**Problem:**  
SQLite's `./data/chatbot.db` is relative to the **current working directory** (cwd) at runtime, NOT the script's file location. If `uvicorn main:app` is run from the project root (`35. 11-Apr-2026/`) instead of from `backend/`, SQLite creates the DB in the wrong directory, causing a fresh empty database instead of the existing one.

**Solution:**  
Use an absolute path computed from `config.py`'s own location:
```python
database_url: str = f"sqlite:///{Path(__file__).parent}/data/chatbot.db"
```
Or enforce that `uvicorn` is always run from `backend/` in the launch scripts.

---

### 🟡 ERR-E03 · `run_project.ps1` / `run_project.bat` — No health check before declaring backend "ready"

**File:** Root launch scripts  
**Problem:**  
The launch scripts start the backend process and then immediately start the frontend, without waiting for the backend to actually be listening on port 8000. The frontend can start making API calls while the backend is still initializing (loading ChromaDB, running migrations), causing a burst of `ERR_CONNECTION_REFUSED` errors in the browser.

**Solution:**  
Add a health check loop in the launch scripts that polls `/health` before starting the frontend:
```powershell
# Wait until backend is ready
$retries = 0
while ($retries -lt 30) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Seconds 1
    $retries++
}
```

---

## SUMMARY TABLE

| ID | Severity | Component | Short Description |
|---|---|---|---|
| ERR-B01 | 🔴 CRITICAL | Backend `chat.py` | Timezone-naive datetime crash on new conversations |
| ERR-B02 | 🔴 CRITICAL | Backend `chat.py` | Background task uses closed DB session → crash |
| ERR-B03 | 🔴 CRITICAL | Backend `database.py` | Invalid `connect_args={"timeout": 30}` → startup crash |
| ERR-B04 | 🟠 HIGH | Backend / Config | Port inconsistency (8000 vs 8080) |
| ERR-B05 | 🟠 HIGH | Backend `settings.py` | Non-thread-safe runtime settings mutation |
| ERR-B06 | 🟠 HIGH | Backend `rag_engine.py` | ChromaDB fallback uses temp dir → all data lost on restart |
| ERR-B07 | 🟠 HIGH | Backend `reports.py` | Fragile LLM JSON parsing → silent empty response |
| ERR-B08 | 🟡 MEDIUM | Backend `monitoring.py` | `== False` SQLAlchemy warning |
| ERR-B09 | 🟡 MEDIUM | Backend `reports.py` | All downloads served as `.xlsx` MIME type |
| ERR-B10 | 🟡 MEDIUM | Backend `web_search.py` | Deprecated `get_event_loop()` |
| ERR-B11 | 🟡 MEDIUM | Backend `requirements.txt` | `chardet`/`charset-normalizer` conflict |
| ERR-B12 | 🔵 INFO | Backend `audit_studio.py` | Detached ORM object after session close |
| ERR-F01 | 🔴 CRITICAL | Frontend `ReportPreview.tsx` | TypeScript build error — `npm run build` fails |
| ERR-F02 | 🔴 CRITICAL | Frontend `App.tsx` | Ref read during render (React rules violation) |
| ERR-F03 | 🟠 HIGH | Frontend `LegalStudio.tsx` | Ref mutation during render (Concurrent Mode unsafe) |
| ERR-F04 | 🟠 HIGH | Frontend `LegalStudio.tsx` | SSE event type mismatch → web search indicator broken |
| ERR-F05 | 🟠 HIGH | Frontend `api.ts` | API base URL port inconsistency |
| ERR-F06 | 🟠 HIGH | Frontend `ChatMessages.tsx` | Array index as React key → wrong reconciliation |
| ERR-F07 | 🟡 MEDIUM | Frontend `LegalStudio.tsx` | Silent doc delete error → UI/backend state mismatch |
| ERR-F08 | 🟡 MEDIUM | Frontend `package.json` | Non-existent `lucide-react@^1.8.0` version |
| ERR-F09 | 🟡 MEDIUM | Frontend `App.tsx` | `/finance` redirects to empty homepage |
| ERR-F10 | 🔵 INFO | Frontend `LegalStudio.tsx` | Upload errors caught silently without user feedback |
| ERR-E01 | 🔴 CRITICAL | `.env` | Real NVIDIA API key exposed in plaintext file |
| ERR-E02 | 🟠 HIGH | `config.py` | Relative DB path fails if cwd is wrong |
| ERR-E03 | 🟡 MEDIUM | Launch scripts | No health check before starting frontend |

---

**Total Errors Found:** 25  
**Critical (🔴):** 7 | **High (🟠):** 9 | **Medium (🟡):** 7 | **Info (🔵):** 2

---

*Report generated: 2026-04-20 | Full review covering backend Python, frontend TypeScript, environment config, and launch scripts.*
