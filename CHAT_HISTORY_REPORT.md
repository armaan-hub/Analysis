# Chat History Report

## Overview

**Database:** `backend/data/chatbot.db`

| Metric | Value |
|--------|-------|
| **Total Conversations** | 302 |
| **Total Messages** | 162 |
| **Export Date** | 2026-04-27 08:20 UTC+4 |

---

## Conversations by Mode

| Mode | Conversations | % of Total |
|------|---------------|-----------|
| **Fast Mode** | 236 | 78.1% |
| **Analyst Mode** | 65 | 21.5% |
| **Deep Research** | 1 | 0.3% |
| **TOTAL** | 302 | 100% |

---

## Recent Conversations (Last 15)

### 1. Electronic Invoicing Explained
- **ID:** 40528233-5bfb-4a07-8e5a-0fb19c7a29d3
- **Mode:** Fast
- **Created:** 2026-04-27 03:56:12
- **Provider:** NVIDIA (nvidia/llama-3.3-nemotron-super-49b-v1)
- **Messages:** 2

### 2. VAT Payment For Hotel Apartment Sale (Deep Research)
- **ID:** 7d615ff6-8d9c-4e4a-9f1e-2c5e8f8b4c2a
- **Mode:** Deep Research
- **Created:** 2026-04-26 19:51:18
- **Provider:** NVIDIA (nvidia/llama-3.3-nemotron-super-49b-v1)
- **Messages:** 1

### 3. I have a client who sold Hotel Apartment and now got notice... (Analyst)
- **ID:** b6cc69ad-7f4e-4c5b-8d2e-3a9e1f8b5c1a
- **Mode:** Analyst
- **Created:** 2026-04-26 19:51:18
- **Provider:** NVIDIA (nvidia/llama-3.3-nemotron-super-49b-v1)
- **Messages:** 1

### 4. VAT Payment For Hotel Apartment Sale (Fast - 3-turn conversation)
- **ID:** f38e83e1-0194-460a-bc84-cd548624673d
- **Mode:** Fast
- **Created:** 2026-04-26 19:49:48
- **Provider:** NVIDIA (nvidia/llama-3.3-nemotron-super-49b-v1)
- **Messages:** 6
- **Turns:**
  1. User: "I have a client who sold Hotel Apartment and now got notice from FTA to pay VAT, need a one pager on this as well documents required to make payment on portal"
  2. Assistant: One-pager with VAT details (3,096 tokens)
  3. User: "Please format this as a proper one-pager with clear sections"
  4. Assistant: Formatted response (3,494 tokens)
  5. User: "Give me the exact step-by-step process to pay on the FTA EmaraTax portal with the specific documents checklist"
  6. Assistant: Portal steps with documents checklist (4,021 tokens)

### 5-15. Various VAT-related Conversations
- VAT Deep Research Test (fast)
- VAT Hotel Apt Test 2 (fast)
- VAT Hotel Apt Test (fast)
- VAT Hotel Test (fast)
- explain me E-invoicing (fast)
- Client Received VAT Notice After Selling Hotel Apartment (fast) × 3

---

## Database Tables

| Table | Rows | Purpose |
|-------|------|---------|
| **conversations** | 302 | Chat sessions |
| **messages** | 162 | Messages within conversations |
| **documents** | 286 | Uploaded/indexed documents |
| **research_jobs** | 14 | Background research jobs |
| **account_mappings** | 204 | Account reference mappings |
| **templates** | 1 | Chat templates |
| Others | 0 | (Empty) |

---

## Key Findings

### Most Common Query Topics
- **VAT on Hotel Apartment Sales** — 20+ conversations
- **E-invoicing** — 3+ conversations
- **General accounting/legal questions** — 279+ conversations

### Model Performance
- **Primary Model:** nvidia/llama-3.3-nemotron-super-49b-v1
- **Primary Provider:** NVIDIA NIM
- **Average Response Tokens:** ~3,500 per turn

### Usage Patterns
- **Fast Mode:** Primary usage (78% of conversations)
- **Analyst Mode:** Secondary usage (21.5%)
- **Deep Research:** Minimal (0.3%)
- **Average Messages per Conversation:** 0.5 messages (many single-turn queries)

---

## Export Files

- **JSON Export:** `chat_history_export.json` (full conversation data with message previews)
- **This Report:** `CHAT_HISTORY_REPORT.md` (summary and statistics)

---

## How to Access Chat Data

### Via Backend API
```bash
GET /api/chat/conversations              # List all conversations
GET /api/chat/conversations/{conv_id}    # Get specific conversation
```

### Via Database (SQLite)
```sql
SELECT * FROM conversations ORDER BY created_at DESC;
SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at;
```

### Via Frontend
Open `http://localhost:5173` → Chat page → View conversation history

---

## Data Retention

- **Auto-cleanup:** None configured
- **Database size:** ~2-3 MB (SQLite file at `backend/data/chatbot.db`)
- **Backup:** Manual only (recommend backing up `backend/data/`)

---

**Report Generated:** 2026-04-27 08:20 UTC+4
