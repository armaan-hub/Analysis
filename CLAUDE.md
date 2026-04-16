# CLAUDE.md — Accounting & Legal AI Chatbot

## Project Overview

Multi-platform AI chatbot for accounting and legal professionals.
- **Backend**: Python + FastAPI — fully built, running at `http://localhost:8000`
- **Frontend**: React + Vite + TypeScript — 30% complete, actively being built
- **Desktop**: Electron — not started yet

## Project Structure

```
Project_AccountingLegalChatbot/
├── backend/          # Python FastAPI — complete
│   ├── main.py
│   ├── config.py
│   ├── core/         # llm_manager, rag_engine, document_processor, report_generator
│   ├── api/          # chat, documents, reports, monitoring, settings
│   ├── monitoring/   # scheduler, scrapers
│   └── db/           # models, database
├── frontend/         # React + Vite + TypeScript — in progress
│   └── src/
│       ├── components/   # Chat/, Documents/, Reports/, Alerts/, Settings/
│       ├── pages/
│       └── App.tsx
└── desktop/          # Electron — not started
```

## Development Commands

```bash
# Backend (Python)
cd backend
uv run python main.py
# Docs at http://localhost:8000/docs

# Frontend (React)
cd frontend
npm run dev
# UI at http://localhost:5173
```

## Current Focus

Frontend UI components — build these in order:
1. Chat interface (messages + input box)
2. Document upload panel (drag-and-drop)
3. Report generation form (IFRS, VAT, Corporate Tax)
4. Alerts display (regulatory changes)
5. Settings panel (LLM provider selector)

## API Endpoints (Backend → Frontend contract)

| Purpose | Endpoint |
|---------|----------|
| Send chat message | `POST /api/chat/send_message` |
| Upload document | `POST /api/documents/upload` |
| Generate report | `POST /api/reports/` |
| Get alerts | `GET /api/monitoring/` |
| Configure LLM | `PUT /api/settings/` |

## Key Rules for Claude

- **Read only the file(s) needed to fix a specific error** — do not scan the entire codebase
- Fix one error at a time; do not refactor surrounding code
- Backend is complete — do not modify backend files unless explicitly asked
- Frontend uses TypeScript — keep all types correct
- Design system: glassmorphism, dark theme
- API base URL for frontend: `http://localhost:8000`
- Do not add features beyond what is asked
- Do not add comments or docstrings to code you didn't change
- Security: API keys live in `.env` only, never in source code

## Environment / Config

`.env` file in project root:
```
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=your_key_here
DATABASE_URL=sqlite:///chatbot.db
RAG_MODEL=nvidia/embed-qa-4
```

## When Fixing Errors

1. Read the error message carefully
2. Read only the specific file(s) involved
3. Apply the minimal fix
4. Do not touch unrelated code
