# 📋 Accounting & Legal AI Chatbot – Complete Project Overview

## 🎯 What Is This Project?

This is a **multi-platform AI chatbot application** (web + desktop) designed for accounting and legal professionals. It helps them:
- Ask questions about legal and financial documents
- Generate professional accounting reports (IFRS, VAT, Corporate Tax)
- Stay updated on regulatory changes automatically

**Status**: Backend is fully built and running. Frontend UI is being developed.

---

## 🏗️ How Does It Work?

### 1. **The Brain (Multi-LLM Engine)**
The system can use different AI providers (OpenAI, Claude, Mistral, NVIDIA, Ollama) without changing code. Think of it like having a smart assistant that can be powered by different AI engines.

### 2. **The Knowledge Base (RAG System)**
- Users upload documents (PDF, Word, Excel)
- The system breaks documents into chunks and stores them in a searchable database (ChromaDB)
- When a user asks a question, the system finds relevant document chunks and adds them to the prompt for the AI
- This ensures answers are **backed by actual documents**

### 3. **Automatic Report Generation**
The system can create professional Excel files for:
- **IFRS Financial Statements** (Income Statement, Balance Sheet)
- **VAT Returns** (UAE FTA format)
- **Corporate Tax Returns** (UAE 9% calculation)

### 4. **Regulatory Monitoring**
- A background scheduler checks law and tax websites every 6 hours
- If changes are detected, it creates alerts that users can see
- This replaces manual checking for compliance updates

---

## 📁 Project Structure Explained

```
Project_AccountingLegalChatbot/
│
├── backend/                          # The "Engine" (Python + FastAPI)
│   ├── main.py                       # Entry point - starts the API server
│   ├── config.py                     # Configuration (API keys, settings)
│   │
│   ├── core/                         # Core business logic
│   │   ├── llm_manager.py            # Switches between AI providers
│   │   ├── rag_engine.py             # Document search & retrieval
│   │   ├── document_processor.py     # Reads PDF/Word/Excel
│   │   └── report_generator.py       # Creates Excel reports
│   │
│   ├── api/                          # API Endpoints (what the UI talks to)
│   │   ├── chat.py                   # /chat endpoint (send messages)
│   │   ├── documents.py              # /documents endpoint (upload files)
│   │   ├── reports.py                # /reports endpoint (generate Excel)
│   │   ├── monitoring.py             # /monitoring endpoint (alerts)
│   │   └── settings.py               # /settings endpoint (configure LLM)
│   │
│   ├── monitoring/                   # Background tasks
│   │   ├── scheduler.py              # Runs checks on schedule
│   │   └── scrapers/                 # Monitors specific websites
│   │
│   └── db/                           # Database layer
│       ├── models.py                 # Database tables (schema)
│       └── database.py               # Database connection & sessions
│
├── frontend/                         # The "UI" (React + TypeScript)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/                 # Message display & input
│   │   │   ├── Documents/            # File upload panel
│   │   │   ├── Reports/              # Report generation form
│   │   │   ├── Alerts/               # Regulatory alerts display
│   │   │   └── Settings/             # LLM provider selector
│   │   ├── pages/                    # Full page views
│   │   └── App.tsx                   # Main app component
│   └── package.json                  # NPM dependencies
│
└── desktop/                          # Desktop app wrapper (Electron)
    └── main.js                       # Electron configuration
```

---

## ✅ What's Done? 🎉

### Backend (100% Complete)
- ✅ **Multi-LLM Factory**: Can switch between 5+ AI providers
- ✅ **RAG System**: Document upload, parsing, and intelligent search
- ✅ **Report Generator**: IFRS, VAT, and Corporate Tax Excel generation
- ✅ **Regulatory Monitoring**: Background scheduler with alerts
- ✅ **Database**: SQLite for storing conversations, documents, alerts
- ✅ **API Endpoints**: All backends routes are built and tested

### Frontend (30% Complete)
- ✅ React + Vite setup (modern, fast)
- ✅ TypeScript configuration
- ✅ Design system (glassmorphism styling)
- ⏳ Chat interface (messages + input)
- ⏳ Document upload panel
- ⏳ Report generation form
- ⏳ Alerts notification display
- ⏳ Settings panel

### Desktop (Not Started)
- ⏳ Electron wrapper for Windows & Mac

---

## 🔌 How Each Part Connects

```
User opens web browser
         ↓
   [ React Frontend ]  (Chat UI, Document Upload, etc.)
         ↓
   Makes HTTP calls to...
         ↓
[ FastAPI Backend ]
         ├─→ LLM Manager → Calls OpenAI/Claude/NVIDIA
         ├─→ RAG Engine → Searches ChromaDB
         ├─→ Report Generator → Creates Excel files
         └─→ Database → Stores/retrieves data
```

---

## 🚀 Key Technologies

| Component | Technology | Why? |
|-----------|-----------|------|
| **Backend** | Python + FastAPI | Fast, async, perfect for AI/ML |
| **RAG** | LangChain + ChromaDB | Industry-standard for document search |
| **Document Parsing** | PyMuPDF, python-docx, openpyxl | Read PDF, Word, Excel |
| **AI Providers** | OpenAI, Claude, Mistral, NVIDIA | Multiple options, no lock-in |
| **Frontend** | React + Vite + TypeScript | Modern, fast, type-safe |
| **Desktop** | Electron | Windows & Mac from same code |
| **Database** | SQLite | Easy, no setup needed |

---

## 🎯 Current Status

### ✅ Backend is **Running** (RAG fully indexed, LLM reliability in progress)
- API server is running at `http://localhost:8000`
- All business logic is implemented and tested
- Database auto-initializes on startup

### 🔄 Frontend is **Under Development**
- The UI structure is set up, but individual screens need to be built
- Each screen (Chat, Documents, Reports, Alerts) connects to the backend API

### 📊 Next Steps
1. **Complete Chat Interface** → Let users send messages and see AI responses
2. **Implement Document Upload** → File drag-and-drop
3. **Build Report Panel** → Form to input data and generate Excel
4. **Add Alerts Display** → Show regulatory changes in real-time
5. **Package as Desktop App** → Create Windows/Mac installers

---

## 🔑 Key Features Explained

### Feature 1: Smart Document Chat
```
User: "What are the VAT thresholds in the UAE?"
         ↓
Backend:
  1. Searches uploaded documents for "VAT"
  2. Finds relevant paragraphs about thresholds
  3. Adds them to the prompt
  4. Sends to AI with context
         ↓
AI Response: "Based on the document: The VAT threshold is..."
```

### Feature 2: Automatic Report Generation
```
User: Input transaction data (sales, purchases, expenses)
         ↓
Backend:
  1. Receives data
  2. Calculates totals and taxes
  3. Formats into Excel with professional styling
  4. Returns Excel file for download
         ↓
User: Downloads complete VAT return ready for filing
```

### Feature 3: Regulatory Alerts
```
Background Task (every 6 hours):
  1. Visits UAE FTA website
  2. Compares content to last known version
  3. If changes found → Creates alert in database
         ↓
User: Sees notification: "VAT rates updated on 2026-04-12"
```

---

## 📊 Database Schema (What Gets Stored)

The SQLite database stores:
- **Conversations**: Chat history (who asked what, when)
- **Messages**: Individual chat messages with context
- **Documents**: Info about uploaded files (name, size, upload date)
- **Alerts**: Regulatory monitoring findings

All data is stored locally (no cloud required).

---

## 🎨 Design Approach

The frontend uses a **glassmorphism design system** (modern, semi-transparent UI elements) with:
- Clean, professional appearance
- Dark theme for reduced eye strain
- Responsive layout (works on desktop and tablets)

---

## 🔒 Security Notes

- **API Keys**: Stored in `.env` file (not in code)
- **LLM Keys**: Stored locally, never sent to backend
- **Documents**: Stored on user's machine
- **Database**: SQLite file on disk

---

## 📈 Performance Characteristics

- **Chat Response Time**: 30-180 seconds (NVIDIA NIM; varies by model load)
- **Document Upload**: Near-instant (async processing)
- **Report Generation**: 2-10 seconds
- **Regulatory Checks**: Background (doesn't block UI)

---

## 🛠️ Development Commands

```bash
# Start backend
cd backend
uv run python main.py
# API available at http://localhost:8000/docs

# Start frontend
cd frontend
npm run dev
# UI available at http://localhost:5173

# Run tests
cd backend
uv run pytest
```

---

## 📝 Configuration

Create `.env` file in project root:
```
LLM_PROVIDER=nvidia  # or openai, claude, mistral, ollama
NVIDIA_API_KEY=your_key_here
NVIDIA_MODEL=google/gemma-4-31b-it
NVIDIA_EMBED_MODEL=nvidia/nv-embedqa-e5-v5
DATABASE_URL=sqlite:///./data/chatbot.db
PORT=8000
```

---

## 🎓 Understanding the Code Flow

### When User Asks a Question:
1. Frontend sends message to `/api/chat/send`
2. Backend receives it
3. Searches RAG system for relevant documents
4. Adds context to LLM prompt
5. Calls the AI provider (NVIDIA/OpenAI/etc)
6. Stores conversation in database
7. Returns response to frontend

### When User Uploads a Document:
1. Frontend sends file to `/api/documents/upload`
2. Backend processes the file (extract text)
3. Chunks text into pieces
4. Embeds each chunk (creates vector representation)
5. Stores in ChromaDB
6. Saves metadata in database

---

## ✨ What Makes This Special

1. **No Vendor Lock-in**: Can swap AI providers with a config change
2. **Document-Backed Answers**: Not just making things up (RAG)
3. **Compliance-Ready**: Generates official accounting documents
4. **Automated Compliance**: Monitors regulations so you don't have to
5. **Cross-Platform**: Web, Windows, Mac from same codebase

---

## 📞 Support Resources

- **Backend API Docs**: `http://localhost:8000/docs` (interactive)
- **Project Vision**: See `memory/project_accounting_legal_chatbot.md`
- **Implementation Details**: See `brain/implementation_plan.md`
- **Progress Tracking**: See `brain/task.md`

---

## 🎯 Vision

> "One AI chatbot for all accounting and legal professionals' needs—combining intelligent document analysis, automated compliance reporting, and proactive regulatory monitoring, all on any platform (web, Windows, Mac)."

---

**Last Updated**: April 12, 2026  
**Project Status**: Backend Complete | Frontend In Progress  
**Current Focus**: Building React UI components
