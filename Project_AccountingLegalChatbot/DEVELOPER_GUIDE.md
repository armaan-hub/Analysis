# Developer Guide — Accounting & Legal AI Chatbot

Complete reference for setting up, running, testing, and contributing to the project.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [First-Time Setup](#first-time-setup)
3. [Environment Configuration](#environment-configuration)
4. [Running the Project](#running-the-project)
5. [Backend Development](#backend-development)
6. [Frontend Development](#frontend-development)
7. [Testing](#testing)
8. [Codebase Walkthrough](#codebase-walkthrough)
9. [Key Design Decisions](#key-design-decisions)
10. [Contributing](#contributing)
11. [Troubleshooting](#troubleshooting)

---

## System Requirements

| Dependency | Minimum | Notes |
|------------|---------|-------|
| Python | 3.11+ | 3.12 recommended |
| Node.js | 20 LTS+ | Required for frontend & desktop |
| npm | 9+ | Comes with Node.js |
| Git | Any | |
| Tesseract OCR | 5.x | **Optional** — only needed for scanned Arabic PDFs |
| Poppler | Any | **Optional** — required by pdf2image for OCR |

### Installing Tesseract (Optional, Windows)

```powershell
# Install via winget (Windows 10/11)
winget install UB-Mannheim.TesseractOCR

# Or download installer from: https://github.com/UB-Mannheim/tesseract/wiki
# Ensure tesseract.exe is on PATH, or set PDF_OCR_TESSERACT_CMD in .env
```

---

## First-Time Setup

### 1. Clone / Navigate to Project

```powershell
# The project lives inside the class directory:
cd "C:\Users\<you>\...\35. 11-Apr-2026\Project_AccountingLegalChatbot"
```

### 2. Install All Dependencies (One Command)

```powershell
# Creates backend Python venv + installs all pip packages + npm packages
.\install_all_dependencies.ps1

# Force recreate venv (if you hit version conflicts):
.\install_all_dependencies.ps1 -RecreateVenv
```

What this script does:
1. Creates `backend/venv/` Python virtual environment
2. Upgrades pip/setuptools/wheel
3. Installs `backend/requirements.txt`
4. Downloads the `en_core_web_sm` spaCy language model
5. Runs `npm ci` (or `npm install`) in `frontend/`
6. Runs `npm ci` in `desktop/` if `package.json` exists there

### 3. Configure Environment

```powershell
Copy-Item backend\.env.example backend\.env
# Open backend\.env in your editor and fill in at least one API key
```

Minimum required: **one LLM provider API key** (NVIDIA recommended for first run).

### 4. Verify Installation

```powershell
# Quick backend smoke test (no live LLM needed):
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q --tb=short
cd ..
```

All 426 tests should pass.

---

## Environment Configuration

All backend config lives in `backend/.env`. See `backend/.env.example` for the full template.

### Minimal .env for Development

```env
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=google/gemma-4-31b-it
EMBEDDING_PROVIDER=nvidia
NVIDIA_EMBED_MODEL=nvidia/nv-embedqa-e5-v5

DATABASE_URL=sqlite:///./data/chatbot.db
UPLOAD_DIR=./uploads
VECTOR_STORE_DIR=./vector_store_v2
```

### Switching LLM Providers

Change `LLM_PROVIDER` to any of: `nvidia` | `openai` | `claude` | `mistral` | `groq` | `ollama`

Then supply the matching key and model variables. You can also switch providers at runtime via the Settings page in the UI, or via `POST /api/settings/providers/switch`.

### Config Loading

`backend/config.py` uses **pydantic-settings**. All values can be overridden by environment variables (case-insensitive). Relative paths (upload_dir, vector_store_dir, database_url) are resolved relative to `backend/`.

---

## Running the Project

### Development (Recommended)

```powershell
# From project root — starts both services with auto-restart:
.\run_project.ps1
```

This launcher:
- Starts backend on **port 8001** via uvicorn with `--reload`
- Starts frontend on **port 5173** via Vite dev server
- Auto-restarts either service if it crashes (up to 5 times)
- Streams logs to console + `backend_server.log` / `frontend_server.log`
- Press **Ctrl+C** to stop both cleanly

### Running Individually

```powershell
# Backend only:
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Frontend only:
cd frontend
npm run dev
```

### Production Build (Frontend)

```powershell
cd frontend
npm run build
# Output → frontend/dist/
# Serve dist/ with any static file server or Nginx
```

---

## Backend Development

### Entry Point

`backend/main.py` — FastAPI app with lifespan hooks:
- Initialises SQLite DB + runs schema migrations
- Seeds account-mapping cache from CSV
- Starts APScheduler (regulatory monitoring)
- Starts auto-sync watchdog (monitors `data_source_*/`)

### Adding a New API Route

1. Create `backend/api/my_feature.py` with a `router = APIRouter(prefix="/api/my-feature")`
2. Register it in `main.py`: `app.include_router(my_feature_router)`

### Adding a New LLM Provider

1. Add config fields to `Settings` in `backend/config.py`
2. Add a branch to `LLMManager` in `backend/core/llm_manager.py`
3. Add to `active_api_key` and `active_model` property maps
4. Update `.env.example`

### RAG / Document Ingestion Flow

```
Upload file
    │
    ▼
DocumentProcessor.process(file)     # Parse text (PyMuPDF / python-docx / openpyxl)
    │                               # OCR fallback for scanned PDFs
    ▼
RAGEngine.ingest_chunks(chunks)     # Chunk text, embed, store in ChromaDB
    │                               # Metadata: domain, doc_id, original_name
    ▼
HybridRetriever.search(query)       # Dense (cosine) + sparse (BM25) retrieval
    │
    ▼
chat.py._build_rag_domain_filter()  # Domain-scoped search (no cross-domain leakage)
```

**Domain mapping** (set at ingest time via `_infer_domain_from_name`):

| Domain | Triggered by filename containing |
|--------|----------------------------------|
| `e_invoicing` | e_invoicing, peppol |
| `vat` | vat |
| `corporate_tax` | corporate_tax |
| `labour` | labour |
| `commercial` | commercial |
| `ifrs` / `general` | ifrs, general |
| *(no filter)* | general_law, general |

### Database Models

`backend/db/models.py` — SQLAlchemy async models:
- `Conversation` — chat thread (title, domain, mode, pinned, summary)
- `Message` — individual message (role, content, sources JSON, tokens)
- `Document` — indexed file record
- `AuditProfile`, `Template` — studio-specific models

Migrations: `backend/db/migrations/` — run idempotently on every startup via `lifespan`.

---

## Frontend Development

### Stack

- **React 19** + **TypeScript** + **Vite 8**
- **react-router-dom v7** for routing
- **axios** for API calls (base URL configured in `src/api-config.ts`)
- **recharts** for financial charts
- **@tanstack/react-table** for data tables
- **lucide-react** for icons
- **react-markdown** + **remark-gfm** for AI response rendering

### Key Files

```
src/
├── api-config.ts          # Axios instance with base URL (http://localhost:8001)
├── App.tsx                # Top-level router
├── pages/
│   ├── HomePage.tsx       # Main chat interface + studio switcher
│   └── SettingsPage.tsx   # LLM provider settings
└── components/
    ├── studios/
    │   ├── FinanceStudio/     # Trial balance, IFRS reports
    │   ├── LegalStudio/       # Legal Q&A, document search
    │   ├── AuditStudio/       # Audit workflows
    │   ├── TemplateStudio/    # Report templates
    │   └── RegulatoryStudio/  # Alerts, monitoring
    ├── common/                # Shared: buttons, modals, loaders
    └── StudioSwitcher.tsx     # Studio navigation tabs
```

### Changing the Backend URL

Edit `src/api-config.ts` — change the `baseURL`:
```typescript
const api = axios.create({ baseURL: "http://localhost:8001" });
```

For production deployments, set the URL via a Vite env variable:
```typescript
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8001" });
```

---

## Testing

### Backend Tests

```powershell
cd backend

# All unit tests (fast, no API keys required):
.\venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q

# Specific test file:
.\venv\Scripts\python.exe -m pytest tests/test_chat_endpoint_domain.py -v

# With coverage:
.\venv\Scripts\python.exe -m pytest tests/ -m "not integration" --cov=. --cov-report=term-missing -q

# Integration tests (requires live API keys):
$env:RUN_LLM_TESTS="1"
.\venv\Scripts\python.exe -m pytest tests/ -m integration -v
```

### Test Configuration

`backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    integration: marks tests requiring a live LLM (deselect with '-m "not integration"')
```

**`conftest.py`** provides:
- In-memory SQLite test database (isolated per test)
- `httpx.AsyncClient` with `ASGITransport` for API testing
- Mock LLM/RAG fixtures

### Frontend Tests

```powershell
cd frontend
npm test            # Run vitest in watch mode
npm run test -- --run  # Run once (CI mode)
```

### Writing New Backend Tests

```python
# tests/test_my_feature.py
import pytest
from httpx import AsyncClient

async def test_my_endpoint(client: AsyncClient):
    response = await client.post("/api/my-feature/action", json={"key": "value"})
    assert response.status_code == 200
    assert response.json()["result"] == "expected"
```

Use `@pytest.mark.integration` for tests that need a live LLM.

---

## Codebase Walkthrough

### `backend/core/` — Business Logic

| Module | Purpose |
|--------|---------|
| `llm_manager.py` | Single entry point for all LLM calls; handles provider routing |
| `rag_engine.py` | ChromaDB CRUD: `ingest_chunks`, `delete_document`, `search`, `get_stats` |
| `document_processor.py` | Parses PDF/DOCX/XLSX; OCR fallback via Tesseract |
| `report_generator.py` | Generates IFRS / VAT / Corp Tax structured reports |
| `rag/hybrid_retriever.py` | Combines dense cosine similarity + BM25 sparse scores |
| `council/council_service.py` | Orchestrates 4-expert panel → synthesis |
| `council/personas.py` | Frozen `Expert` dataclasses: CA, CPA, CMA, Analyst |
| `research/query_decomposer.py` | Decomposes complex queries into sub-questions (deep mode) |
| `pipeline/auto_sync.py` | Watchdog on `data_source_*/` — auto-ingests new files |
| `monitoring/scheduler.py` | APScheduler jobs for regulatory scraping |
| `agents/` | Account placement, batch template learner, auto-verifier |
| `audit_studio/` | Audit workflow engine, audit formatter |

### `backend/api/` — Route Handlers

Each file is a FastAPI `APIRouter`. Handlers are thin: they call `core/` services, validate inputs with Pydantic schemas, and return typed responses.

### `backend/db/`

Async SQLAlchemy with aiosqlite. `database.py` exposes a `get_db` dependency injected into route handlers. All models use UUID primary keys.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Hybrid RAG (dense + BM25)** | Pure cosine similarity misses short legal terms (VAT, AED, LLC). BM25 catches exact keyword matches. |
| **Domain-scoped RAG** | Prevents cross-domain hallucination (e.g., tax law leaking into IFRS answers). Empty results = correct, not a fallback trigger. |
| **Background tasks for title generation** | Avoids race condition where title LLM runs before DB commit. FastAPI `BackgroundTasks` guarantees post-response scheduling. |
| **Council mode (4 experts)** | Single LLM has blind spots. Panel of CA/CPA/CMA/Analyst with synthesis chair covers all accounting perspectives. |
| **Pydantic-settings for config** | Type-safe, env-overridable, documented. No config parsing bugs. |
| **`asyncio_mode=auto` in pytest** | All test coroutines run without explicit `@pytest.mark.asyncio` decorators. |

---

## Contributing

### Branch Naming

```
feature/short-description
fix/short-description
docs/short-description
```

### Commit Convention

```
type(scope): short description

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Pull Request Checklist

- [ ] All unit tests pass: `pytest tests/ -m "not integration" -q`
- [ ] New features have test coverage
- [ ] `.env.example` updated if new env vars added
- [ ] `requirements.txt` pinned if new Python packages added
- [ ] No secrets committed (check `.gitignore`)

### Adding a New Studio

1. **Backend**: Create `api/my_studio.py` router + `core/my_studio/` logic
2. **Register**: `app.include_router(my_studio_router)` in `main.py`
3. **Frontend**: Create `src/components/studios/MyStudio/` components
4. **Navigation**: Add studio tab to `StudioSwitcher.tsx`

---

## Troubleshooting

### Backend won't start

```powershell
# Check Python venv exists:
Test-Path backend\venv\Scripts\python.exe

# Reinstall deps:
.\install_all_dependencies.ps1 -RecreateVenv
```

### "Vector store dimension mismatch" error

This happens when you switch embedding models. Delete and recreate the vector store:
```powershell
Remove-Item -Recurse -Force backend\vector_store_v2
# Restart the backend — it will create a fresh empty store
# Re-upload your documents or re-run bulk_ingest.py
```

### ChromaDB corruption

```powershell
Remove-Item -Recurse -Force backend\vector_store_v2
# Restart backend
```

### Frontend proxy errors (CORS)

Ensure `backend/.env` has `HOST=0.0.0.0` and backend is running on port 8001. Check `frontend/src/api-config.ts` points to `http://localhost:8001`.

### Tesseract not found (OCR)

```powershell
# Option 1: Add tesseract to PATH (restart terminal after install)
# Option 2: Set explicit path in .env:
echo "PDF_OCR_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe" >> backend\.env
```

### Port 8001 already in use

```powershell
# Find the process:
netstat -ano | Select-String ":8001"
# Kill it:
Stop-Process -Id <PID> -Force
```

### Port 5173 already in use

`run_project.ps1` automatically kills lingering Vite processes on ports 5173–5179 before starting. If you run the frontend manually, kill the old process first.

---

*Last updated: April 2026 | Authors: Armaan, Copilot*
