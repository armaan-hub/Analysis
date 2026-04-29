# 🏛️ Accounting & Legal AI Chatbot

> **Version:** v2.0 | **Status:** ✅ Production-ready | **Tests:** 426 passing

A full-stack AI chatbot platform for accounting and legal professionals. Built on FastAPI + React with Hybrid RAG (ChromaDB + BM25), multi-LLM switching, and dedicated professional studios for audit, legal, finance, and council advisory workflows.

---

## ✨ Feature Overview

| Category | Features |
|----------|----------|
| **AI Chat** | Multi-LLM support, RAG-grounded answers, streaming responses, conversation history |
| **RAG Engine** | Hybrid retrieval (dense + sparse), domain-scoped search, OCR for Arabic/English PDFs |
| **Studios** | Finance Studio, Legal Studio, Audit Studio, Template Studio, Regulatory Studio |
| **Council Mode** | Multi-expert panel: CA (IFRS), CPA (US GAAP), CMA (costing), Financial Analyst |
| **Document Processing** | PDF, Word, Excel upload; auto-chunking, vector indexing, domain tagging |
| **Financial Reports** | IFRS statements, UAE VAT returns, corporate tax filings, trial balance analysis |
| **Regulatory Monitoring** | Scheduled scraping, automated alerts for UAE law/finance/tax changes |
| **LLM Providers** | NVIDIA NIM, OpenAI, Claude (Anthropic), Mistral, Groq, Ollama (local) |
| **Deployment** | Web app (React + Vite) + Windows/macOS Electron desktop app |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  Chat UI · Finance Studio · Legal Studio             │
│  Audit Studio · Council Mode · Regulatory Monitor    │
│              http://localhost:5173                   │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────▼────────────────────────────────┐
│               Backend (FastAPI)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ Chat API │ │ Docs API │ │Reports   │  ...more     │
│  └────┬─────┘ └────┬─────┘ └──────────┘             │
│       │             │                                │
│  ┌────▼──────────────▼──────────────────────────┐   │
│  │            Core Business Logic               │   │
│  │  LLM Manager · Hybrid RAG · Council Service  │   │
│  │  Document Processor · Report Generator       │   │
│  └─────────┬─────────────┬───────────────────── ┘   │
│            │             │                           │
│  ┌─────────▼──┐  ┌───────▼────────┐                 │
│  │  SQLite DB │  │  ChromaDB      │                 │
│  │ (chatbot)  │  │ (vector store) │                 │
│  └────────────┘  └────────────────┘                 │
└─────────────────────────────────────────────────────┘
              http://localhost:8001
```

---

## 🚀 Quick Start (Windows)

### Prerequisites
- Python 3.11+
- Node.js 20+
- Tesseract OCR (for scanned Arabic PDFs) — optional

### 1. Install All Dependencies

```powershell
# From the Project_AccountingLegalChatbot/ directory:
.\install_all_dependencies.ps1

# First time or to recreate the venv:
.\install_all_dependencies.ps1 -RecreateVenv
```

### 2. Configure Environment

```powershell
Copy-Item backend\.env.example backend\.env
# Edit backend\.env with your API keys (see Configuration section below)
```

### 3. Launch

```powershell
# Starts backend (port 8001) + frontend (port 5173) with auto-restart:
.\run_project.ps1
```

| Service | URL |
|---------|-----|
| Frontend (Web UI) | http://localhost:5173 |
| Backend API | http://localhost:8001 |
| API Documentation | http://localhost:8001/docs |
| Health Check | http://localhost:8001/health |

---

## ⚙️ Configuration

Edit `backend/.env` (copy from `backend/.env.example`):

### LLM Provider Selection

```env
# Choose one: nvidia | openai | claude | mistral | groq | ollama
LLM_PROVIDER=nvidia
```

### API Keys by Provider

| Provider | Key Variable | Notes |
|----------|-------------|-------|
| NVIDIA NIM | `NVIDIA_API_KEY` | Default provider; free tier available |
| OpenAI | `OPENAI_API_KEY` | GPT-4o default |
| Anthropic | `ANTHROPIC_API_KEY` | Claude Sonnet default |
| Mistral | `MISTRAL_API_KEY` | mistral-large-latest |
| Groq | `GROQ_API_KEY` | Free tier, fast inference |
| Ollama | — | Local; no key needed |

### RAG & Storage

```env
VECTOR_STORE_DIR=./vector_store_v2    # ChromaDB path
UPLOAD_DIR=./uploads                   # Uploaded document storage
DATABASE_URL=sqlite:///./data/chatbot.db
EMBEDDING_PROVIDER=nvidia              # nvidia | openai
```

### OCR (Scanned Arabic PDFs)

```env
PDF_OCR_ENABLED=true
PDF_OCR_LANGUAGES=ara+eng
PDF_OCR_DPI=300
# PDF_OCR_TESSDATA_DIR=./tessdata     # Optional: custom traineddata path
# PDF_OCR_TESSERACT_CMD=              # Optional: explicit tesseract path
```

---

## 📁 Project Structure

```
Project_AccountingLegalChatbot/
├── backend/                          # FastAPI Python backend
│   ├── main.py                       # Application entry point
│   ├── config.py                     # Typed settings (pydantic-settings)
│   ├── requirements.txt              # Python dependencies
│   ├── api/                          # HTTP route handlers
│   │   ├── chat.py                   # Chat endpoints + streaming
│   │   ├── documents.py              # Upload, index, search docs
│   │   ├── reports.py                # Financial report generation
│   │   ├── audit_studio.py           # Audit Studio API
│   │   ├── legal_studio.py           # Legal Studio API
│   │   ├── council.py                # Multi-expert Council API
│   │   ├── monitoring.py             # Regulatory alerts API
│   │   ├── settings.py               # LLM provider switching
│   │   ├── templates.py              # Report templates API
│   │   └── audit_profiles.py         # Audit profiles API
│   ├── core/                         # Business logic
│   │   ├── llm_manager.py            # Multi-provider LLM client
│   │   ├── rag_engine.py             # RAG engine (ingest / search)
│   │   ├── document_processor.py     # PDF/Word/Excel parsing + OCR
│   │   ├── report_generator.py       # IFRS / VAT / CIT report gen
│   │   ├── rag/                      # Hybrid retrieval
│   │   │   ├── hybrid_retriever.py   # Dense + BM25 hybrid search
│   │   │   └── graph_rag.py          # Graph-based RAG (experimental)
│   │   ├── council/                  # Multi-expert council
│   │   │   ├── personas.py           # CA, CPA, CMA, Analyst experts
│   │   │   └── council_service.py    # Council orchestration
│   │   ├── chat/                     # Chat processing
│   │   ├── audit_studio/             # Audit workflow engine
│   │   ├── research/                 # Deep research + query decomposition
│   │   ├── agents/                   # AI agents (account placement etc.)
│   │   └── pipeline/                 # Auto-sync data pipeline
│   ├── db/                           # Database layer
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── database.py               # Async SQLite connection
│   │   └── migrations/               # Schema migration scripts
│   ├── monitoring/                   # Regulatory change monitoring
│   │   ├── scheduler.py              # APScheduler jobs
│   │   └── scrapers/                 # UAE law/finance scrapers
│   └── tests/                        # 426 pytest tests
│       ├── conftest.py               # Fixtures (async SQLite, HTTP client)
│       └── ...                       # ~60+ test files
├── frontend/                         # React 19 + TypeScript web UI
│   ├── src/
│   │   ├── App.tsx                   # Router + layout
│   │   ├── api-config.ts             # Axios base URL config
│   │   ├── pages/                    # HomePage, SettingsPage
│   │   └── components/
│   │       ├── studios/              # Finance, Legal, Audit, Template, Regulatory
│   │       ├── common/               # Shared UI components
│   │       └── StudioSwitcher.tsx    # Studio navigation
│   ├── package.json                  # npm dependencies (React 19, Vite 8)
│   └── vite.config.ts                # Vite dev server config
├── desktop/                          # Electron desktop app (Windows/macOS)
├── docs/                             # Extended documentation
│   ├── superpowers/specs/            # Design specifications
│   └── Gemini_Sessions/              # AI session notes
├── install_all_dependencies.ps1      # One-shot dependency installer
├── run_project.ps1                   # Dev launcher with auto-restart
├── DEVELOPER_GUIDE.md                # Developer setup & contribution guide
└── .env.example                      # Environment template (backend)
```

---

## 🔌 API Reference

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/send` | Send message; supports `stream=true` |
| `GET` | `/api/chat/conversations` | List all conversations |
| `GET` | `/api/chat/conversations/{id}` | Get conversation with messages |
| `DELETE` | `/api/chat/conversations/{id}` | Delete a conversation |
| `PATCH` | `/api/chat/conversations/{id}/pin` | Pin/unpin conversation |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload & index PDF/Word/Excel |
| `GET` | `/api/documents/` | List indexed documents |
| `DELETE` | `/api/documents/{id}` | Remove document from index |
| `GET` | `/api/documents/search?query=` | Semantic search |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/reports/generate/ifrs` | Generate IFRS financial statement |
| `POST` | `/api/reports/generate/vat` | Generate UAE VAT return |
| `POST` | `/api/reports/generate/corptax` | Generate corporate tax filing |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings/current` | Get current LLM config |
| `GET` | `/api/settings/providers` | List all available providers |
| `POST` | `/api/settings/providers/switch` | Switch active LLM provider |

### Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/monitoring/alerts` | List regulatory alerts |
| `POST` | `/api/monitoring/trigger` | Manually trigger monitoring run |

> Full interactive API docs: **http://localhost:8001/docs** (Swagger UI)

---

## 🤖 Chat Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `fast` | Higher top-k, faster inference | Quick lookups, factual Q&A |
| `deep` | Deep research, query decomposition | Complex analysis, research |
| `analyst` | Financial analyst persona | Financial modelling, valuations |
| `council` | 4-expert panel (CA/CPA/CMA/Analyst) | Multi-perspective advisory |

---

## 🎭 Council Mode — Expert Panel

When `mode=council`, the question is answered by a panel of 4 AI experts, then synthesized:

| Expert | Credentials | Focus |
|--------|-------------|-------|
| **Senior CA** | ICAI/ICAEW, 20+ yrs | Audit, IFRS compliance, ISA procedures |
| **CPA** | US CPA | US GAAP, ASC 606/740, deferred tax |
| **CMA** | Cost & Management | Cost behaviour, variance, transfer pricing |
| **Financial Analyst** | CFA charterholder | DCF, comparable multiples, leverage ratios |

---

## 🧪 Testing

```bash
cd backend

# Run all unit tests (fast, no LLM required)
pytest tests/ -m "not integration" -q

# Run with coverage
pytest tests/ -m "not integration" --cov=. --cov-report=term-missing

# Run integration tests (requires live LLM keys in .env)
RUN_LLM_TESTS=1 pytest tests/ -m integration -v
```

**Current status:** 426 passed, 1 skipped (integration)

---

## 🔄 Document Ingestion

Documents placed in the watched directories are **auto-ingested** on startup and file-change:

```
backend/data_source_finance/   # Finance documents (IFRS, VAT, CIT)
backend/data_source_law/       # Legal documents (UAE law, regulations)
```

Manual upload via the web UI or `POST /api/documents/upload` also triggers immediate ingestion.

**Supported formats:** PDF (text + scanned/OCR), DOCX, XLSX

---

## ⚠️ Security Notes

- **CORS:** The backend is configured with `allow_origins=["*"]` for local development. **Before deploying to a production or shared server, restrict this to your specific frontend origin(s)** in `backend/main.py` (search for `CORSMiddleware`).
- **API Keys:** Never commit `.env` to version control. Use environment secrets in CI/CD.

---

## 📜 License

Private project – Armaan / Data Science Class 2026
