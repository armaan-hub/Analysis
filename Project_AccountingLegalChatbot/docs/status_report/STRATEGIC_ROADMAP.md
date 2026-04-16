# Strategic Project Roadmap: Accounting & Legal AI Chatbot

> **Project**: UAE-focused AI chatbot for Accounting, VAT, Corporate Tax, AML, and Legal Compliance  
> **Stack**: FastAPI · ChromaDB [ACTIVE] · LangChain · React (TypeScript) · Electron  
> **Primary LLM**: NVIDIA NIM (default provider — `llm_provider=nvidia` in `config.py`). OpenAI, Claude, Mistral, and Ollama are optional fallbacks configured via `.env`.  
> **Current Completion**: Phase 1 ~90% · Phase 2 ~75% · Phase 3 ~60% · Phase 4 ~10%

---

## Prerequisites — Required `.env` Variables

Before running the app, create a `.env` file in the project root (copy `.env.example`):

```
LLM_PROVIDER=nvidia               # Primary provider — nvidia | openai | claude | mistral | ollama
NVIDIA_API_KEY=your_key_here      # Required when LLM_PROVIDER=nvidia (get from build.nvidia.com)
OPENAI_API_KEY=                   # Required when LLM_PROVIDER=openai or EMBEDDING_PROVIDER=openai
ANTHROPIC_API_KEY=                # Required when LLM_PROVIDER=claude
MISTRAL_API_KEY=                  # Required when LLM_PROVIDER=mistral
EMBEDDING_PROVIDER=nvidia         # nvidia | openai
DATABASE_URL=sqlite:///./data/chatbot.db
```

If `NVIDIA_API_KEY` is missing and `LLM_PROVIDER=nvidia`, the app will start but embedding/chat calls will fail with a 403 error. Set the key before indexing any documents.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tool Stack — Why Each Tool is Used](#tool-stack--why-each-tool-is-used)
3. [Phase 1 — Knowledge Integrity & Domain Awareness](#phase-1--knowledge-integrity--domain-awareness)
4. [Phase 2 — Reporting Intelligence & Auditor Toolkit](#phase-2--reporting-intelligence--auditor-toolkit)
5. [Phase 3 — Studio Frontend Overhaul](#phase-3--studio-frontend-overhaul)
6. [Phase 4 — Regulatory Alerting & Production Hardening](#phase-4--regulatory-alerting--production-hardening)
7. [Implementation Order & Dependencies](#implementation-order--dependencies)
8. [Completion Checklist](#completion-checklist)

---

## Architecture Overview

```
+---------------------------------------------------------------------------+
|                          USER INTERFACES                                  |
|   React Web UI (Vite + TypeScript)    |   Desktop App (Electron)          |
+-----------------------------+---------------------------------------------+
                              | HTTP / WebSocket
+-----------------------------v---------------------------------------------+
|                       FASTAPI BACKEND  (main.py)                          |
|                                                                           |
|  +----------------+  +----------------+  +-----------------------------+  |
|  |  API Routes    |  | Prompt Router  |  |   LLM Manager              |  |
|  |  /chat         |  | (Domain-aware  |  |   NVIDIA NIM / OpenAI /    |  |
|  |  /documents    |  |  system        |  |   Claude / Mistral /       |  |
|  |  /reports      |  |  prompts)      |  |   Ollama                   |  |
|  |  /monitoring   |  +----------------+  +-----------------------------+  |
|  |  /settings     |                                                       |
|  +----------------+                                                       |
|                                                                           |
|  +------------------------+  +----------------------------------------+  |
|  |   RAG Engine           |  |   Report Generator                     |  |
|  |   LangChain +          |  |   openpyxl / xlsxwriter                |  |
|  |   ChromaDB             |  |   IFRS · VAT 201 · Corporate Tax       |  |
|  +------------------------+  +----------------------------------------+  |
|                                                                           |
|  +------------------------+  +----------------------------------------+  |
|  |   Document Processor   |  |   Monitoring / Scheduler               |  |
|  |   PyMuPDF · docx ·     |  |   APScheduler · BeautifulSoup4        |  |
|  |   openpyxl · OCR       |  |   FTA · MOJ scrapers                  |  |
|  +------------------------+  +----------------------------------------+  |
|                                                                           |
|  +-----------------------------------------------------------------------+|
|  |   SQLite (SQLAlchemy + aiosqlite) — Conversations & History           ||
|  +-----------------------------------------------------------------------+|
+---------------------------------------------------------------------------+
                              |
                 +------------v------------+
                 |   ChromaDB Vector Store |
                 |   (on-disk)             |
                 |   UAE Laws · PDFs       |
                 +-------------------------+
```

---

## Tool Stack — Why Each Tool is Used

Understanding **why** each tool exists prevents choosing the wrong solution and helps you extend the system correctly.

---

### Backend Framework

| Tool | Why We Use It |
|------|---------------|
| **FastAPI** | Async-first Python framework. Gives us auto-generated Swagger docs at `/docs`, WebSocket support for streaming chat, and `async def` endpoints that do not block during LLM calls (which can take 5–30 seconds). |
| **Uvicorn** | ASGI server that runs FastAPI. Handles concurrent requests without threads — critical when 10 users query the LLM at the same time. |
| **Pydantic / pydantic-settings** | Data validation and `.env` config loading. Every API request body is auto-validated — if a field is missing or wrong type, FastAPI returns a clear 422 error before bad data reaches the LLM. |

**Why not Flask/Django?** Flask is sync-only (blocks on LLM calls). Django is too heavy for an API-only service. FastAPI is the modern standard for AI/ML backends.

---

### Database

| Tool | Why We Use It |
|------|---------------|
| **SQLAlchemy** | ORM for SQLite. Maps Python classes to database tables — `Conversation`, `Message`, `Alert` models instead of raw SQL strings. |
| **aiosqlite** | Async SQLite driver. Without this, every DB read/write blocks the entire event loop and freezes all other requests. |
| **SQLite** | Zero-config embedded database. Perfect for a single-server deployment — no separate DB process to manage. Can be swapped to PostgreSQL later via SQLAlchemy. |

**Why not PostgreSQL now?** Overkill for a single-user/small-team tool. SQLite is fast for < 100,000 rows. Migrate to Postgres when you need multi-server or high concurrency.

---

### LLM Integration

| Tool | Why We Use It |
|------|---------------|
| **openai SDK** | Official client for OpenAI GPT-4o and NVIDIA NIM (NIM uses the same OpenAI-compatible API). Handles retries, streaming, and token counting. |
| **anthropic SDK** | Official client for Claude 3.5 Sonnet. Claude is especially strong at long-document analysis (200K context), ideal for reading full UAE law PDFs. |
| **httpx** | The async HTTP client used internally by both SDK libraries. Also used for direct NVIDIA NIM calls when needed. |
| **LLM Manager** (`llm_manager.py`) | Our own abstraction layer. All routes call `llm_manager.chat()` — they never import openai/anthropic directly. This is why switching providers via `/api/settings/providers/switch` works without restarting the server. |

**Why multiple LLMs?** NVIDIA NIM is fast and cost-efficient for standard queries. Claude handles complex, long legal documents better. Ollama enables fully offline operation for sensitive client data.

---

### RAG (Retrieval-Augmented Generation)

| Tool | Why We Use It |
|------|---------------|
| **LangChain** | Orchestration framework. Handles document splitting, embedding pipeline, and the retrieval chain that combines a user question + retrieved chunks into a final LLM prompt. |
| **langchain-text-splitters** | Splits a 200-page UAE law PDF into overlapping 512-token chunks. Overlap ensures a sentence that falls on a chunk boundary is not lost. |
| **ChromaDB** | Local vector database. Stores embedded chunks as high-dimensional vectors. When a user asks a question, we embed it and find the top-K most similar law chunks — this is the "retrieval" in RAG. |
| **NVIDIA NIM / OpenAI Embeddings** | Convert text chunks into vectors. The quality of the embedding model directly determines how accurately the system retrieves relevant law articles. |
| **RAG Engine** (`rag_engine.py`) | Our wrapper around LangChain. Handles the full pipeline: query → embed → search ChromaDB → format context → send to LLM → return answer with source citations. |

**Why RAG instead of just prompting the LLM?** GPT-4o's training data does not include specific UAE cabinet decisions or FTA circulars. RAG injects the exact, up-to-date legal text into every answer. The AI cites the exact Article number because it literally read it from our database.

---

### Document Processing

| Tool | Why We Use It |
|------|---------------|
| **PyMuPDF** (`fitz`) | Fastest Python PDF parser. Extracts structured text, page numbers, and metadata from UAE law PDFs in milliseconds per page. |
| **python-docx** | Reads `.docx` audit reports, contract templates, and legal briefs. Preserves paragraph structure better than converting to PDF first. |
| **openpyxl** | Reads and writes `.xlsx` Trial Balance files. Used to parse client-uploaded financial data and to write the final IFRS/VAT Excel output. |
| **pdf2image + pytesseract** | OCR pipeline for scanned Arabic law PDFs. `pdf2image` renders each PDF page as a high-res image; `pytesseract` (Tesseract OCR engine) extracts Arabic text. |
| **Pillow** | Image processing library used by pytesseract to preprocess pages (increase DPI, convert to grayscale) for better Arabic character recognition. |

**Why OCR?** Many UAE laws (especially older Federal Decrees) exist only as scanned images inside PDFs — they have no embedded text layer. Without OCR, the RAG system would ingest blank documents and the AI would hallucinate answers instead of citing real articles.

---

### Report Generation

| Tool | Why We Use It |
|------|---------------|
| **openpyxl** | Generates richly-formatted Excel workbooks — bold headers, cell borders, merged cells, and currency formatting for IFRS statements. |
| **xlsxwriter** | Used for features openpyxl cannot do easily: charts, conditional formatting, and freeze panes for large VAT transaction tables. |
| **reportlab** | Generates PDF output from Python. Used for producing the final stamped VAT 201 Return as a PDF that cannot be edited (important for audit trail). |

**Why Excel over PDF for financial reports?** Accountants and auditors need to trace and verify every number. Excel lets them click cells to see formulas. PDF is used only for the final "locked" submission copy.

---

### Regulatory Monitoring

| Tool | Why We Use It |
|------|---------------|
| **APScheduler** | Background job scheduler. Runs the FTA and MOJ scrapers every 6 hours without requiring a separate cron job or Celery setup. Runs inside the FastAPI process. |
| **BeautifulSoup4** | HTML parser for scraping `tax.gov.ae` and `moj.gov.ae` to detect new Cabinet Decisions, VAT circulars, and law amendments. |
| **requests** | Synchronous HTTP client used by the scrapers (the scheduler runs them in a thread pool, not the async event loop). |

**Why scrape instead of using an API?** The UAE government does not publish a public API for regulatory updates. Web scraping is the only automated way to detect changes.

---

### Frontend

| Tool | Why We Use It |
|------|---------------|
| **React + TypeScript** | Component-based UI with type safety. TypeScript catches API shape mismatches at compile time — if the backend changes a response field, TypeScript errors appear in the IDE before the user sees a bug. |
| **Vite** | Ultra-fast development server and bundler. Hot Module Replacement means frontend changes appear in the browser in under 100ms without a full page reload. |
| **Zustand** *(planned)* | Minimal global state manager. The "active studio", "active domain", and "current document" must be accessible from any component. Zustand does this with 10 lines vs Redux's 100+. |
| **Tailwind CSS** *(planned)* | Utility-first CSS. Glassmorphism effects (frosted glass panels) are `backdrop-blur-md bg-white/10` — no custom CSS files needed. Currently the app uses custom CSS classes in `index.css`. |
| **Framer Motion** *(planned)* | Animation library. Handles smooth slide-in of the Document Peeker pane and studio-switching transitions without hand-written CSS keyframes. |
| **TanStack Table** ✅ installed | Headless table library used in `AuditGrid.tsx`. Handles sorting, filtering, and virtual scrolling of thousands of transaction rows without performance issues. |
| **Recharts** *(planned)* | React charting library for the Tax Exposure Dashboard — visual bar chart of quarterly VAT liability and corporate tax accruals. Built on SVG, exports cleanly to PDF. |

> **Multi-language UI**: Arabic language support in OCR (`ara+eng` in `document_processor.py`) is active. However, there is **no UI language toggle** and the AI responses are in English only. Full Arabic UI/response language switching is **planned, not implemented**.|

---

### Desktop App

| Tool | Why We Use It |
|------|---------------|
| **Electron** | Packages the React frontend + a local copy of the FastAPI backend into a single `.exe` / `.dmg` installer. Users get a desktop experience with no browser setup. |
| **electron-builder** | Generates signed MSI (Windows) and DMG (macOS) installers. Handles auto-update channels so clients always run the latest version. |

**Why Electron and not just a web app?** Clients with strict data governance (law firms, audit firms) cannot use cloud-hosted tools. Electron lets them run 100% on-premise — no data leaves their machine.

---

## Phase 1 — Knowledge Integrity & Domain Awareness

**Status**: ~90% Complete  
**Objective**: The AI must be accurate, domain-aware, and able to read all UAE laws including Arabic-only documents.

---

### 1.1 Fix NVIDIA Embedding API ~~(CRITICAL BLOCKER)~~ — **RESOLVED**

> **Status**: Embedding pipeline confirmed working — `total_documents = 439`, `indexed_documents = 439`, `error_documents = 0`. 9 backend tests passing. Check `EMBEDDING_PROVIDER` in `.env` to confirm which provider is active (NVIDIA or fallback).

**Problem (historical)**: The NVIDIA NIM embedding API was returning `403 Forbidden`, preventing all new document ingestion into ChromaDB.

**Why this matters**: Every document uploaded goes through: `text → NIM embedding → ChromaDB`. If the embedding step is broken, new laws cannot be indexed and the RAG system answers from an incomplete knowledge base.

**Implementation**:
```python
# backend/core/rag_engine.py
# Switch to OpenAI embeddings as fallback:
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",  # 1536 dims, same as NIM
    api_key=settings.openai_api_key
)
```

**Resolution path**:
1. Obtain a fresh NVIDIA NIM API key from `build.nvidia.com`
2. If unavailable, fall back to `text-embedding-3-small` (OpenAI) — same 1536-dim vectors, ChromaDB is model-agnostic
3. Add `EMBEDDING_PROVIDER=nvidia|openai` to `.env` so it is switchable without code changes

**Files**: `rag_engine.py` · `config.py` · `.env`

---

### 1.2 Ingest Remaining Arabic Laws via OCR

> **OCR pipeline status**: ✅ Implemented — `_ocr_pdf_page()` in `document_processor.py` handles scanned PDFs with `pytesseract` + `Pillow` fallback. `ara+eng` language support is active. The pipeline is not a future feature; it runs automatically when a PDF has no embedded text layer.

**Remaining task**: 8 Arabic-language UAE laws in `data_source_law/` have not yet been ingested. Run the manual ingestion script to index them.

**Problem**: 8 Arabic-language UAE laws are in `data_source_law/` as scanned PDFs. They have not been indexed because OCR was deferred pending the embedding fix.

**Why this matters**: UAE VAT Federal Decree-Law No. 8 of 2017 and AML Cabinet Decision No. 10 of 2019 are Arabic-primary. Without them, the AI cannot cite original Arabic articles.

**Implementation**:
```bash
# After fixing embedding, run:
cd backend
venv\Scripts\python.exe manual_ocr_fix.py
```

**Why Tesseract over cloud OCR?** Privacy. Client law documents must not leave the local machine. Tesseract is open-source and runs entirely offline.

**Files**: `manual_ocr_fix.py` · `pytesseract` · `pdf2image` · `tessdata/ara.traineddata` · `rag_engine.py`

---

### 1.3 Sharpen Domain Personas in Prompt Router

**Status**: Basic domains exist (finance, law, audit, general). Need specialist sub-prompts.

**Why this matters**: An AML query ("Is this transaction pattern suspicious?") and a VAT query ("Can I claim input tax on this?") both route to `finance` today — the AI gives a generalist answer instead of citing KYC/CDD procedures or FTA Article 54 specifically.

**Implementation** — add to `backend/core/prompt_router.py`:

```python
DOMAIN_PROMPTS["vat"] = (
    "You are a UAE VAT Specialist. You operate under Federal Decree-Law No. 8 of 2017 "
    "and its Executive Regulations. Cite the specific Article and Cabinet Decision number, "
    "calculate VAT at 5% standard rate (or 0% / exempt where applicable), reference FTA "
    "public clarifications, and flag partial exemption situations. Default currency: AED. "
    "Always note FTA filing deadlines." + FORMATTING_SUFFIX
)

DOMAIN_PROMPTS["aml"] = (
    "You are a UAE AML/CFT Compliance Officer. You operate under Federal Decree-Law No. 20 "
    "of 2018 (AML), Cabinet Decision No. 10 of 2019 (CDD), and CBUAE guidelines. "
    "Specify KYC/CDD requirements, describe STR/SAR filing procedures to the Financial "
    "Intelligence Unit (FIU), identify red flags per FATF typologies, and outline penalties "
    "under Article 14 of the AML Law." + FORMATTING_SUFFIX
)

DOMAIN_PROMPTS["legal"] = (
    "You are a UAE Legal Researcher. You specialise in Federal Decree-Laws, Civil Transactions "
    "Law (Federal Law No. 5 of 1985), Commercial Companies Law (Federal Decree-Law No. 32 of "
    "2021), and Employment Law (Federal Decree-Law No. 33 of 2021). Clarify mainland vs "
    "free-zone jurisdiction for every answer. Cite the exact Article number and law title. "
    "Always recommend consulting a licensed UAE lawyer for binding legal advice." + FORMATTING_SUFFIX
)
```

**Files**: `prompt_router.py` · `chat.py` (API route) · Frontend domain selector UI

---

## Phase 2 — Reporting Intelligence & Auditor Toolkit

**Status**: ~75% Complete  
**Objective**: Professional-grade financial output matching what a Big 4 firm would produce.

---

### 2.1 Trial Balance Mapper ✅ IMPLEMENTED

> **Classification note**: The mapper's `_classify_account()` function uses keyword matching to return broad categories (`assets | liabilities | equity | revenue | expenses | other`). This is a simplified approximation — it is **not** a strict IFRS chart-of-accounts mapping. Do not describe it as "IFRS-compliant classification" in user-facing output.

**Problem**: Every client sends their Trial Balance in a different Excel format. Column names vary: "Account Name" vs "Ledger Description" vs "Account Title". The `report_generator.py` currently receives a hard-coded data dict and cannot parse a real client file.

**Why this matters**: This is the #1 blocker for the reporting workflow. Without it, users cannot upload their own Trial Balance to generate IFRS statements.

**Create**: `backend/core/trial_balance_mapper.py`

```python
"""
Trial Balance Mapper — normalises any client Excel TB to the standard schema.
Standard output: [{ "account_code", "account_name", "category", "debit", "credit" }]
"""
import pandas as pd

CATEGORY_KEYWORDS = {
    "assets":      ["asset", "cash", "receivable", "inventory", "property", "equipment", "prepaid"],
    "liabilities": ["liability", "payable", "loan", "overdraft", "provision", "deferred"],
    "equity":      ["equity", "capital", "retained", "reserve", "share"],
    "revenue":     ["revenue", "income", "sales", "fee", "commission"],
    "expenses":    ["expense", "cost", "depreciation", "salaries", "rent", "utilities"],
}

COLUMN_ALIASES = {
    "account_code": ["account code", "acct code", "gl code", "code", "account no"],
    "account_name": ["account name", "account title", "description", "ledger"],
    "debit":        ["debit", "dr", "debit amount", "debit balance"],
    "credit":       ["credit", "cr", "credit amount", "credit balance"],
}

def map_trial_balance(file_path: str) -> list[dict]:
    """Read any .xlsx Trial Balance and return normalized rows."""
    df = pd.read_excel(file_path, header=None)
    # 1. Detect header row (first row where 3+ cells are non-numeric strings)
    # 2. Fuzzy-match column names using COLUMN_ALIASES
    # 3. Classify each account into CATEGORY using KEYWORD matching
    # 4. Return list of normalized dicts
    ...
```

**Why pandas?** Excel files from clients have merged cells, multi-row headers, and blank rows. `pandas.read_excel()` handles these gracefully. Raw openpyxl cell-walking would need 200+ lines of brittle code.

**Add to requirements.txt**: `pandas==2.2.3`

**Files**: `trial_balance_mapper.py` (new) · `requirements.txt` · `reports.py` API route

---

### 2.2 Audit Report Expansion

**Objective**: Add IFRS 9 and IFRS 16 automated notes, and the Independent Auditor's Report template.

**Why generate Notes programmatically?** IFRS 9 and IFRS 16 notes require values from the Trial Balance (e.g., lease liability opening balance, effective interest rate). Pre-filled templates with live numbers eliminate the manual copy-paste that causes audit adjustments.

**Extend** `backend/core/report_generator.py`:

```python
async def generate_audit_report(self, data: dict, company_name: str) -> str:
    """
    Generates a full audit package:
    - Sheet 1: Independent Auditor's Report (ISA 700 template)
    - Sheet 2: IFRS Financial Statements
    - Sheet 3: Note — Financial Instruments (IFRS 9)
    - Sheet 4: Note — Leases (IFRS 16)
    """
```

**Files**: `report_generator.py` · `xlsxwriter` (IFRS 16 lease schedule chart) · `reportlab` (PDF lock copy)

---

### 2.3 VAT 201 Precision Improvements ⚠️ PARTIALLY COMPLETE

> **Per-emirate breakdown status**: Previously all standard-rated sales were hardcoded to Box 1b (Dubai only). The `VatTransaction` model now has an optional `emirate` field and `generate_vat_return()` groups transactions by emirate (Boxes 1a–1g). Transactions without an `emirate` value fall into Box 1g as "unspecified". A disclaimer is written to cell A5 of the generated workbook. **VAT 201 output should not be submitted to the FTA without professional review.**

**Objective**: Handle partial exemption (businesses with both taxable and exempt supplies) and de-registration threshold checking.

**Add to** `backend/api/reports.py`:

```python
def calculate_partial_exemption(
    taxable_supplies: float,
    exempt_supplies: float,
    total_input_tax: float
) -> dict:
    """Partial Exemption Ratio = Taxable / (Taxable + Exempt). Per FTA Article 54."""
    if (taxable_supplies + exempt_supplies) == 0:
        return {"per": 0, "recoverable_input_tax": 0, "irrecoverable_input_tax": 0}
    per = taxable_supplies / (taxable_supplies + exempt_supplies)
    return {
        "per": round(per, 4),
        "recoverable_input_tax": round(total_input_tax * per, 2),
        "irrecoverable_input_tax": round(total_input_tax * (1 - per), 2),
    }

def check_deregistration_threshold(annual_taxable_supplies: float) -> bool:
    """Returns True if business is below AED 187,500 de-registration threshold (FTA Article 21)."""
    return annual_taxable_supplies < 187_500
```

**Files**: `reports.py` · `report_generator.py` · `xlsxwriter` (VAT return Excel)

---

## Phase 3 — Studio Frontend Overhaul

**Status**: ~30% Complete (StudioSwitcher component exists, pages stubbed)  
**Objective**: A professional dual-studio workspace that looks and feels like a premium compliance SaaS product.

---

### 3.1 Dual-Studio Architecture

**Why "Studio" layout?** Legal research chat vs financial report generation are completely different UX patterns. Mixing them on one page confuses users. Separate studios (like Adobe Lightroom modules) let each workflow be optimised independently.

```
+---------+------------------------------------------------------------+
| Sidebar |                    MAIN WORKSPACE                         |
|         |                                                            |
|  Law    |  LEGAL STUDIO                                              |
|  Icon   |  +----------------------+----------------------------+     |
|         |  |  Chat Stream         |  Document Peeker           |     |
|  Fin    |  |                      |  [PDF page auto-shown      |     |
|  Icon   |  |  > Ask about        |   when AI cites Article]   |     |
|         |  |    Article 54       |                            |     |
|  Alert  |  +----------------------+----------------------------+     |
|  Icon   |                                                            |
|         |  FINANCIAL STUDIO                                          |
|  Sett.  |  Step 1: Upload TB -> Step 2: Audit -> Step 3: Preview -> Step 4: Export
+---------+------------------------------------------------------------+
```

---

### 3.2 Legal Studio — Split-Pane with Document Peeker

**Component**: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

**Why Split-Pane?** When the AI answers "As per Article 54 of Federal Decree-Law No. 8...", users currently must open a separate PDF viewer to verify. The Document Peeker eliminates this context switch — the source page appears automatically in the right pane.

**Backend change** — update `rag_engine.py` to return source metadata:
```python
return {
    "answer": llm_response,
    "sources": [
        {
            "document": doc.metadata["source"],
            "page": doc.metadata["page"],
            "chunk": doc.page_content[:200]
        }
        for doc in retrieved_docs
    ]
}
```

**Frontend** — the Document Peeker currently renders a text excerpt panel (`SourcePeeker.tsx`). Full PDF page rendering with `react-pdf` is planned but not yet implemented.

> **Status**: `react-pdf` is **not installed**. `SourcePeeker.tsx` shows a text excerpt only. To implement the PDF-page pane as described, run `npm install react-pdf` and update `SourcePeeker.tsx` to use `<Document>` / `<Page>` from `react-pdf`.

**Why react-pdf over an iframe?** iframes require a full PDF viewer UI with toolbars. `react-pdf` renders a single page as a canvas element — clean, no toolbars, styled to match the Glassmorphism theme.

**Install** (when implementing): `npm install react-pdf framer-motion`

---

### 3.3 Financial Studio — Stepper Workflow

**Component**: `frontend/src/components/studios/FinancialStudio/FinancialStudio.tsx`

**Why Stepper?** Report generation has a mandatory sequence — you cannot preview before uploading, cannot export before previewing. A stepper UI makes the sequence explicit and prevents user confusion.

| Step | Component | Library | Why |
|------|-----------|---------|-----|
| Step 1: Upload | FileDropzone | react-dropzone | Drag-and-drop for `.xlsx` Trial Balance files |
| Step 2: Audit | AIAuditPanel | Streaming SSE | AI streams audit findings line by line (no long spinner wait) |
| Step 3: Preview | DataGrid | TanStack Table | Virtual-scroll for thousands of rows without lag |
| Step 4: Export | ExportButton | Blob download API | Downloads Excel/PDF without a page reload |

**Why TanStack Table over AG Grid?** AG Grid community has commercial licence restrictions. TanStack Table is MIT-licensed, headless (bring your own styles), and integrates perfectly with Tailwind CSS.

**Install**: `npm install @tanstack/react-table react-dropzone recharts`

---

### 3.4 Glassmorphism Design System

**Why Glassmorphism?** It communicates "precision and clarity" — appropriate for a legal/financial tool. The frosted-glass effect layers panels without blocking content, critical in the split-pane Legal Studio where users read both the chat and the PDF simultaneously.

**Base CSS** — `frontend/src/index.css`:
```css
.glass-panel {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
}
```

**Tailwind shorthand** (planned — Tailwind is **not yet installed**):
```tsx
<div className="backdrop-blur-md bg-white/[0.08] border border-white/15 rounded-xl">
```
> **Note**: Tailwind CSS is listed as *(planned)* and is not in `package.json`. The app currently uses the `.glass-panel` custom CSS utility class defined in `index.css`. The Tailwind shorthand above produces no effect until Tailwind is installed and configured (`npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`).

---

### 3.5 Global State Management with Zustand

**Why Zustand over Context API?** Active studio, selected domain, current document, and API key status are needed by 8+ components. Passing these through React props creates "prop drilling" — changing one value requires updating 5 files. Zustand provides a global store with zero boilerplate.

**Create**: `frontend/src/lib/store.ts`
```typescript
import { create } from 'zustand';

interface AppState {
  studio: 'legal' | 'financial' | 'regulatory' | 'settings';
  domain: 'vat' | 'aml' | 'legal' | 'finance' | 'audit' | 'general';
  activeDocumentId: string | null;
  setStudio: (s: AppState['studio']) => void;
  setDomain: (d: AppState['domain']) => void;
  setActiveDocument: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  studio: 'legal',
  // Note: third studio value is 'regulatory' (not 'monitoring')
  domain: 'general',
  activeDocumentId: null,
  setStudio: (studio) => set({ studio }),
  setDomain:  (domain) => set({ domain }),
  setActiveDocument: (activeDocumentId) => set({ activeDocumentId }),
}));
```

**Install**: `npm install zustand`

---

## Phase 4 — Regulatory Alerting & Production Hardening

**Status**: ~10% Complete  
**Objective**: Make the system proactive (real-time alerts) and deployable (installers).

---

### 4.1 Real-Time Frontend Alerts via WebSocket

**Problem**: The scraper runs every 6 hours and writes alerts to SQLite. The frontend only sees them by polling — users miss time-sensitive Cabinet Decisions.

**Why WebSocket over polling?** Polling sends a request every 30 seconds even when nothing changed — wasted bandwidth and server load. WebSocket maintains one persistent connection; the server pushes a message only when a new alert arrives.

> **⚠ Multi-worker limitation**: `_connected_clients` in `monitoring.py` is a module-level list that lives in a single process's memory. Under `uvicorn --workers N > 1`, each worker maintains its own list — a `broadcast_alert()` fired from Worker 2's APScheduler cannot reach WebSocket clients connected to Worker 1. **Current deployment must use a single worker** (`uvicorn main:app --workers 1`). To support multi-worker scaling, replace the in-process list with **Redis Pub/Sub**: all workers subscribe to a shared channel and any worker can publish a message that reaches every connected client. Add `redis` and `aioredis` to `requirements.txt` when implementing this.

**Backend** — `backend/api/monitoring.py`:
```python
from fastapi import WebSocket
import asyncio

connected_clients: list[WebSocket] = []  # single-worker only — see warning above

@router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(60)
            await websocket.send_json({"type": "ping"})
    except Exception:
        connected_clients.remove(websocket)

async def broadcast_alert(alert: dict):
    """Called by the scheduler when a new regulation is detected."""
    for ws in connected_clients:
        await ws.send_json({"type": "alert", "data": alert})
```

**Frontend** — `frontend/src/lib/websocket.ts`:
```typescript
const ws = new WebSocket('ws://localhost:8000/ws/alerts');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'alert') {
    useAppStore.getState().addAlert(msg.data);  // triggers toast notification
  }
};
```

**Files**: `monitoring.py` · `scheduler.py` · `frontend/src/lib/websocket.ts`

---

### 4.2 Offline Mode for Desktop App

**Objective**: Law firms with strict data policies need the system to run with zero internet access.

**Implementation**:
1. Bundle a stripped ChromaDB vector store (UAE laws only) into the Electron app's resources folder
2. Use Ollama with `llama3.2:3b` or `phi3:mini` as the offline LLM
3. Add `OFFLINE_MODE=true` to the desktop `.env` — `llm_manager.py` checks this flag and routes to Ollama

**Why Ollama for offline?** Ollama runs quantized (4-bit) models that fit in 8GB RAM. `llama3.2:3b` is fast enough for Q&A — the answer quality comes from RAG, not the LLM alone.

**Files**: `llm_manager.py` · `config.py` · Electron `app.getPath('userData')` for local ChromaDB path

---

### 4.3 Production Packaging

**Windows MSI** — `desktop/electron-builder.json`:
```json
{
  "appId": "com.eracorporations.legalai",
  "win": {
    "target": "msi",
    "signingHashAlgorithms": ["sha256"]
  },
  "msi": {
    "oneClick": false,
    "perMachine": true,
    "runAfterFinish": true
  }
}
```

**macOS DMG**:
```json
"mac": {
  "target": "dmg",
  "category": "public.app-category.business",
  "hardenedRuntime": true
}
```

**Auto-update**: Use `electron-updater` pointing to a private GitHub Releases channel. Clients get update notifications without IT intervention.

**Tools**: `electron-builder` · `electron-updater` · GitHub Actions (CI builds)

---

## Implementation Order & Dependencies

```
Phase 1.1  Fix NVIDIA embedding API
    |
    +-- Phase 1.2  OCR Arabic laws  (needs working embeddings)
    |       |
    |       +-- Phase 1.3  Domain prompts  (completes RAG accuracy)
    |
Phase 2.1  Trial Balance Mapper
    |
    +-- Phase 2.2  Audit Report Expansion  (needs normalized TB data)
    |
    +-- Phase 2.3  VAT 201 Precision  (independent, run in parallel)

Phase 3.1  Dual-Studio Architecture (routing + layout)  <-- start frontend here
    |
    +-- Phase 3.2  Legal Studio  (depends on store + rag_engine source metadata)
    |
    +-- Phase 3.3  Financial Studio  ✅ DONE (7-step stepper)
    |
    +-- Phase 3.4  Glassmorphism styles  (parallel, no dependencies)
    |
    +-- Phase 3.5  Zustand global store  (depends on Phase 3.1)

Phase 4.1  WebSocket alerts  (depends on Phase 3 store for alert state)
Phase 4.2  Offline mode  (independent)
Phase 4.3  Production packaging  (last, after all features complete)
```

---

## Completion Checklist

### Phase 1 — Knowledge Integrity
- [x] **1.1** Resolve embedding API 403 — **RESOLVED**: embedding pipeline confirmed working (439 docs indexed, 0 errors). Check `EMBEDDING_PROVIDER` in `.env` to confirm active provider.
- [ ] **1.2** Run `manual_ocr_fix.py` — ingest all 8 remaining Arabic laws into ChromaDB
- [x] **1.3a** Add `vat`, `aml`, `legal` domains to `prompt_router.py` — implemented (lines 46–81, also includes `corporate_tax`)
- [x] **1.3b** Domain selector implemented in `LegalStudio.tsx` (lines 138–177) — `ChatPage.tsx` is a dead/orphaned file and is not used
- [x] **1.3c** Pass selected domain: frontend → `/api/chat/send` → `prompt_router.get_system_prompt()` — `LegalStudio.tsx` line 60 sends `domain` in request body

### Phase 2 — Reporting
- [x] **2.1a** Add `pandas==2.2.3` to `requirements.txt` — already at line 32 of `backend/requirements.txt`
- [x] **2.1b** Create `backend/core/trial_balance_mapper.py` with fuzzy column detection — file exists at `backend/core/trial_balance_mapper.py`
- [x] **2.1c** Wire mapper into `POST /api/reports/upload-trial-balance` endpoint — implemented in `backend/api/reports.py` lines 183–210
- [ ] **2.2** Add IFRS 9 and IFRS 16 note sheets to `report_generator.py`
- [ ] **2.2** Add Independent Auditor's Report template sheet (ISA 700)
- [x] **2.3a** Implement `calculate_partial_exemption()` in `reports.py` — implemented at lines 258–282
- [x] **2.3b** Implement `check_deregistration_threshold()` in `reports.py` — implemented at lines 285–305

### Phase 3 — Frontend
- [ ] **3.1 (Dual-Studio)** `npm install zustand framer-motion react-pdf react-dropzone recharts` (`@tanstack/react-table` already installed at `^8.21.3`)
- [ ] **3.2 (Legal Studio)** Create `frontend/src/lib/store.ts` (Zustand global store)
- [ ] **3.2 (Legal Studio)** Build `LegalStudio.tsx` with split-pane + Document Peeker (react-pdf)
- [ ] **3.2 (Legal Studio)** Update `rag_engine.py` to return `sources[].page` metadata
- [x] **3.3 (Financial Studio)** `FinancialStudio.tsx` 7-step stepper workflow — implemented
- [ ] **3.4 (Glassmorphism)** Extend `glass-panel` utility class usage across all panels
- [ ] **3.5 (Zustand)** Create `frontend/src/lib/store.ts` for global studio/domain/document state
- [ ] **3.6 (Recharts)** Integrate Recharts for Tax Exposure dashboard

### Phase 4 — Production
- [ ] **4.1** Add WebSocket endpoint `/ws/alerts` to `monitoring.py`
- [ ] **4.2** Wire `broadcast_alert()` into APScheduler job callback
- [ ] **4.3** Add WebSocket client hook in frontend; trigger toast notification on alert
- [ ] **4.4** Configure Ollama offline routing in `llm_manager.py`
- [ ] **4.5** Generate MSI installer with `electron-builder`
- [ ] **4.6** Set up `electron-updater` with GitHub Releases

---

*Last updated: 14 April 2026 | Project: Accounting & Legal AI Chatbot | Era Corporations*
