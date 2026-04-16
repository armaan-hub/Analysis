# 🏛️ Accounting & Legal AI Chatbot

**A comprehensive AI-powered platform for accounting and legal professionals** with RAG-based document analysis, financial report generation, and real-time regulatory monitoring.

---

## 📋 Project Overview

The Accounting & Legal AI Chatbot is an enterprise-grade application designed to:
- **Analyze** financial documents (PDFs, Excel, Word) using advanced AI
- **Generate** regulatory-compliant reports (IFRS, UAE VAT, Tax filings)
- **Monitor** real-time regulatory changes with automated alerts
- **Support** multiple LLM providers (NVIDIA NIM, OpenAI, Claude, Mistral, Ollama)
- **Provide** both web and desktop interfaces for seamless access

### Key Technologies
- **Backend**: FastAPI (Python), SQLAlchemy, LangChain
- **Frontend**: React with Vite, TypeScript
- **Desktop**: Electron
- **LLM Integration**: Multi-provider support (NVIDIA NIM, OpenAI, Claude, Mistral, Ollama)
- **Document Processing**: RAG pipeline with vector embeddings
- **Database**: SQLite/PostgreSQL ready

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.9+**
- **Node.js 16+** (for frontend)
- **npm or yarn**
- **Windows PowerShell** (for setup scripts)

### Step 1: One-Time Setup

Run from the root directory:

```powershell
.\setup_python_env.bat
```

This script will:
- Create Python virtual environment (`Project_AccountingLegalChatbot\backend\venv`)
- Install backend dependencies from `requirements.txt`

### Step 2: Install Frontend Dependencies

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm ci
Set-Location ..\..
```

### Step 3: Configure Environment

```powershell
Copy-Item .\Project_AccountingLegalChatbot\.env.example .\Project_AccountingLegalChatbot\.env -Force
```

**Edit `.env`** and add your API keys:
```
NVIDIA_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
# Other provider keys...
```

### Step 4: Run Backend API

```powershell
Set-Location .\Project_AccountingLegalChatbot\backend
.\venv\Scripts\activate
python main.py
```

✅ **API Running** at `http://localhost:8000`  
📚 **API Docs** at `http://localhost:8000/docs` (Swagger UI)

### Step 5: Run Frontend UI (in new terminal)

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm run dev
```

✅ **Frontend** available at `http://localhost:5173` (Vite default)

---

## 📁 Project Structure

```
Project_AccountingLegalChatbot/
│
├── backend/                          # FastAPI backend
│   ├── main.py                       # Entry point
│   ├── config.py                     # Configuration & settings
│   ├── requirements.txt              # Python dependencies
│   │
│   ├── api/                          # API endpoints
│   │   ├── chat.py                   # Chat/conversation endpoints
│   │   ├── documents.py              # Document upload & search
│   │   ├── reports.py                # Financial report generation
│   │   ├── monitoring.py             # Regulatory monitoring
│   │   └── settings.py               # LLM provider settings
│   │
│   ├── core/                         # Business logic
│   │   ├── llm_manager.py            # LLM provider management
│   │   ├── rag_engine.py             # RAG pipeline
│   │   ├── report_generator.py       # Report generation
│   │   └── monitoring_engine.py      # Regulatory change detection
│   │
│   ├── db/                           # Database layer
│   │   ├── models.py                 # SQLAlchemy models
│   │   ├── database.py               # DB connection & session
│   │   └── schemas.py                # Pydantic schemas
│   │
│   ├── monitoring/                   # Regulatory monitoring
│   │   ├── scrapers/                 # Data scrapers
│   │   └── processors/               # Alert processors
│   │
│   └── tests/                        # Backend tests
│       └── test_*.py
│
├── frontend/                         # React web UI
│   ├── public/
│   ├── src/
│   │   ├── components/               # React components
│   │   ├── pages/                    # Page components
│   │   ├── services/                 # API client services
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── store/                    # State management
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── desktop/                          # Electron desktop app
│   ├── main.js                       # Electron entry
│   ├── preload.js
│   └── package.json
│
├── docs/                             # Documentation
│   ├── API_ENDPOINTS.md
│   ├── SETUP_GUIDE.md
│   ├── ARCHITECTURE.md
│   └── LLM_PROVIDERS.md
│
├── .env.example                      # Environment template
├── README.md                         # This file
└── CLAUDE.md                         # AI interaction notes
```

---

## 🔌 API Endpoints

### Chat Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/send` | Send message, get AI response |
| GET | `/api/chat/conversations` | List all conversations |
| GET | `/api/chat/conversations/{id}` | Get conversation details |
| DELETE | `/api/chat/conversations/{id}` | Delete conversation |

### Document Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload & index document |
| GET | `/api/documents/list` | List indexed documents |
| GET | `/api/documents/search` | Search documents by query |
| DELETE | `/api/documents/{id}` | Delete document |

### Report Generation
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/generate` | Generate financial report |
| GET | `/api/reports/{id}` | Get report details |
| GET | `/api/reports/export` | Export report (PDF/Excel) |

### LLM Provider Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/providers` | List available providers |
| GET | `/api/settings/providers/active` | Get active provider |
| POST | `/api/settings/providers/switch` | Switch provider |

### Regulatory Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/monitoring/alerts` | Get regulatory alerts |
| POST | `/api/monitoring/subscribe` | Subscribe to alerts |
| GET | `/api/monitoring/status` | Monitoring status |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/docs` | Swagger API documentation |
| GET | `/redoc` | ReDoc documentation |
| GET | `/health` | Health check |

---

## ⚙️ Configuration

### Environment Variables

Create `.env` from `.env.example`:

```bash
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=True

# Database
DATABASE_URL=sqlite:///./app.db
# Or use PostgreSQL: postgresql://user:password@localhost/dbname

# LLM Providers (choose one or multiple)
NVIDIA_API_KEY=your_nvidia_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_claude_key
MISTRAL_API_KEY=your_mistral_key

# Default LLM Provider
DEFAULT_LLM_PROVIDER=nvidia_nim

# Document Processing
MAX_UPLOAD_SIZE=50  # MB
VECTOR_DB_PATH=./vector_store

# Monitoring
MONITORING_ENABLED=True
MONITORING_INTERVAL=3600  # seconds (1 hour)

# Security
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## 🧪 Testing

### Backend Tests

```powershell
Set-Location .\Project_AccountingLegalChatbot\backend
.\venv\Scripts\activate
python -m pytest tests -v
```

### Frontend Tests

```powershell
Set-Location .\Project_AccountingLegalChatbot\frontend
npm run test
npm run lint    # ESLint check
npm run build   # Build check
```

---

## ✨ Features Detail

### 1. **Multi-LLM Support**
- Switch between NVIDIA NIM, OpenAI, Claude, Mistral, Ollama
- Provider-specific configurations
- Fallback mechanism if primary provider unavailable

### 2. **RAG Document Analysis**
- Upload: PDFs, Word docs, Excel sheets
- Automatic text extraction and chunking
- Vector embedding for semantic search
- Context-aware responses

### 3. **Financial Reporting**
- **IFRS Compliant** statements
- **UAE VAT Returns** (VAT-2)
- **Corporate Tax** filings
- Automated data extraction from documents
- Export to PDF/Excel

### 4. **Regulatory Monitoring**
- Real-time monitoring of regulatory changes
- Automated alerts for accounting/legal updates
- Email notifications (configurable)
- Change history tracking

### 5. **Multi-Platform**
- **Web UI**: React SPA (http://localhost:5173)
- **Desktop**: Electron app (Windows/macOS)
- **API**: REST endpoints (FastAPI)

---

## 🔐 Security Features

- **Authentication**: JWT tokens (configurable)
- **Rate Limiting**: Per-endpoint rate limits
- **CORS**: Configurable trusted origins
- **Input Validation**: Pydantic schemas
- **API Key Management**: Secure environment variables
- **Database**: SQL injection prevention

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│            http://localhost:5173                     │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼──────────────────────────────────┐
│              Backend API (FastAPI)                   │
│           http://localhost:8000                      │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   Chat API   │  │ Document API │  │ Reports    │ │
│  └────┬─────────┘  └────┬─────────┘  └─────┬──────┘ │
│       │                 │                    │        │
│  ┌────▼──────────────────▼────────────────────▼────┐ │
│  │          Core Business Logic                     │ │
│  │  ┌──────────────┐  ┌──────────────┐            │ │
│  │  │  LLM Manager │  │  RAG Engine  │            │ │
│  │  └──────────────┘  └──────────────┘            │ │
│  └──────────────────────────────────────────────────┘ │
│                      │                                 │
│  ┌───────────────────▼────────────────────────────┐  │
│  │         Database (SQLite/PostgreSQL)           │  │
│  │   Conversations, Documents, Reports, Alerts    │  │
│  └────────────────────────────────────────────────┘  │
│                      │                                │
│  ┌───────────────────▼────────────────────────────┐  │
│  │     Vector Store (for RAG embeddings)          │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## 🛠️ Troubleshooting

### Backend Won't Start
```powershell
# 1. Check Python version
python --version

# 2. Verify virtual environment
.\Project_AccountingLegalChatbot\backend\venv\Scripts\activate

# 3. Reinstall dependencies
pip install -r requirements.txt

# 4. Check logs
type backend_server.err.log
```

### Frontend Port Already in Use
```powershell
# Vite will try next available port automatically
# Or specify port:
cd frontend && npm run dev -- --port 5174
```

### API Documentation Not Loading
- Ensure backend is running: `http://localhost:8000/docs`
- Check CORS settings in `.env`
- Clear browser cache

### LLM Provider Errors
- Verify API keys in `.env`
- Check provider credentials and rate limits
- Review logs in `backend_server.err.log`

---

## 📚 Documentation

- **[Setup Guide](Project_AccountingLegalChatbot/docs/SETUP_GUIDE.md)** - Detailed setup instructions
- **[API Reference](Project_AccountingLegalChatbot/docs/API_ENDPOINTS.md)** - Complete API documentation
- **[Architecture](Project_AccountingLegalChatbot/docs/ARCHITECTURE.md)** - System design & components
- **[LLM Providers](Project_AccountingLegalChatbot/docs/LLM_PROVIDERS.md)** - Provider configuration

---

## 🤝 Contributing

This is a private project for the Data Science Class. For questions or contributions:

1. Document your changes in the code
2. Include test cases for new features
3. Update relevant documentation
4. Use descriptive commit messages

---

## 📄 License

**Private Project** - Armaan / Data Science Class  
All rights reserved. Not for external distribution.

---

## 📞 Support

For issues, questions, or feature requests, refer to:
- Project Documentation: `Project_AccountingLegalChatbot/docs/`
- Code Comments & Docstrings
- API Documentation: `http://localhost:8000/docs` (when running)

---

## 🎯 Project Status

- ✅ **Backend API** - Complete & Functional
- ✅ **Frontend UI** - React SPA implemented
- ✅ **LLM Integration** - Multi-provider support
- ✅ **RAG Engine** - Document analysis working
- ✅ **Report Generation** - IFRS, VAT, Tax reports
- ✅ **Monitoring** - Regulatory alerts active
- 🔄 **Desktop App** - Electron implementation in progress

---

**Last Updated**: April 16, 2026  
**Version**: 1.0.0  
**Author**: Armaan
