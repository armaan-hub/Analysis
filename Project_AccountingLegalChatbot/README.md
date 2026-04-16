# 🏛️ Accounting & Legal AI Chatbot

A multi-platform AI chatbot for accounting and legal professionals featuring RAG-powered document analysis, automated financial report generation, and real-time regulatory monitoring.

## ✨ Features

- **🤖 Multi-LLM Support** – Switch between NVIDIA NIM, OpenAI, Claude, Mistral, and Ollama
- **📄 RAG Document Analysis** – Upload PDFs, Word, Excel files for intelligent Q&A
- **📊 Financial Reporting** – Generate IFRS statements, UAE VAT returns, corporate tax filings
- **🔔 Regulatory Monitoring** – Automated alerts for law/tax/finance regulatory changes
- **🌐 Multi-Platform** – Web interface + Desktop (Windows/macOS)

## 🚀 Quick Start

### 1. Setup Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env` and fill in your API keys:

```bash
copy .env.example .env
# Edit .env with your NVIDIA API key (or other provider)
```

### 3. Run

```bash
cd backend
python main.py
```

The API will be available at **http://localhost:8000**  
Interactive docs at **http://localhost:8000/docs**

## 📁 Project Structure

```
Project_AccountingLegalChatbot/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Central configuration
│   ├── api/                 # API route handlers
│   ├── core/                # Business logic (LLM, RAG, reports)
│   ├── db/                  # Database models & connection
│   └── monitoring/          # Regulatory change monitoring
├── frontend/                # React web UI (Phase 4)
├── desktop/                 # Electron desktop app (Phase 4)
└── docs/                    # Documentation
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/send` | Send a message, get AI response |
| GET | `/api/chat/conversations` | List conversations |
| POST | `/api/documents/upload` | Upload & index a document |
| GET | `/api/documents/search?query=...` | Search indexed documents |
| GET | `/api/settings/providers` | List available LLM providers |
| POST | `/api/settings/providers/switch` | Switch LLM provider |
| GET | `/docs` | Swagger API documentation |

## 📜 License

Private project – Armaan / Data Science Class
