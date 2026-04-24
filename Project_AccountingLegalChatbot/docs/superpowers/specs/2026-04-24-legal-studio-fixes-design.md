# Design: Legal Studio — Three Bug Fixes

**Date:** 2026-04-24  
**Scope:** Three separate defects in the Legal Studio / backend pipeline

---

## Problem Statement

1. **Title display** — Conversation cards on the home page show the raw question text (truncated at 80 chars) instead of a meaningful summary.
2. **VAT answer quality** — Queries about commercial property VAT payment (e.g. Hotel Apartment sale + FTA notice) get a generic TRN-registration answer. The correct answer is: non-registered persons pay via FTA portal "Payment of VAT on Commercial Property Sale" service — no TRN required.
3. **Source contamination + first-message timeout** — `selected_doc_ids` is never forwarded to the backend, so all studios share the same RAG pool. In Fast mode the backend runs 3 LLM calls before sending the first byte, causing the 30 s frontend timeout to fire before any response arrives.

---

## Fix 1 — AI-Generated Conversation Title

### Architecture

- **Backend** (`backend/api/chat.py`): When a new conversation is created (first message), schedule a `background_tasks.add_task()` (FastAPI `BackgroundTasks`, already in the endpoint signature) that calls the LLM with a "summarise to ≤8 words" prompt and updates `conversation.title` in the DB.
- **Conversation title initial value** remains the 80-char truncation so the record is usable immediately if the background task is slow.
- **Frontend** (`HomePage.tsx`): No change needed — the existing `GET /api/chat/conversations` fetch is called after `sendMessage` completes, which will pick up the updated title.

### Title generation prompt

```
Summarise the following user query as a short notebook title (max 8 words, title-case). 
Return ONLY the title — no punctuation at the end, no quotation marks.
Query: {message}
```

### Data flow

```
User sends first message
  → Conversation created with truncated title (immediate)
  → asyncio.create_task(_generate_title(conv_id, message))   ← non-blocking
  → LLM returns 6-8 word title
  → DB updated: conversation.title = generated_title
  → Next time conversations list is refreshed, new title appears
```

---

## Fix 2 — VAT Commercial Property Sale Knowledge

### Root cause

The VAT system prompt in `backend/core/prompt_router.py` only covers TRN registration thresholds and periodic filing. It has no guidance for non-registered persons paying VAT on a one-time commercial property sale.

### Changes

**`backend/core/prompt_router.py` — VAT system prompt addition:**

Append a "Commercial Property VAT Payment" section covering:
- Hotel Apartments, serviced apartments, and furnished commercial units are treated as **commercial property** (not residential) → standard VAT at 5% applies on sale
- A non-registered seller (below AED 375,000 threshold or one-time sale) does **not** need to register for a TRN
- The correct procedure is:
  1. Sign up (not register) on the **FTA e-Services portal** (tax.gov.ae)
  2. Select **"Payment of VAT on Commercial Property Sale"** under Non-Registered Persons
  3. Fill in the property details, VAT amount (5% of sale price), and upload supporting documents
  4. Pay via bank transfer or FTA payment gateway
- **Documents required:** Sale/Transfer Agreement (SPA), Title Deed or Oqood, Emirates ID / Passport of seller, FTA notice (if received), calculation worksheet showing 5% VAT on consideration

Add a **few-shot example** to `FEW_SHOT_EXAMPLES["vat"]`:
```
Q: "My client sold a Hotel Apartment and received an FTA notice to pay VAT. What should they do and what documents are needed?"
A: Hotel Apartments are classified as commercial property under UAE VAT law; the 5% standard rate applies on their sale. Your client is a non-registered person making a one-time taxable supply, so they do NOT need a TRN. 

**One-Pager: VAT Payment on Commercial Property Sale**

**Situation:** Non-registered individual sold a Hotel Apartment; FTA issued a notice to pay VAT.

**Step-by-Step Process:**
1. Go to the FTA e-Services portal: tax.gov.ae
2. Sign up (create a user account — this is NOT VAT registration)
3. Under "Non-Registered Persons", select **Payment of VAT on Commercial Property Sale**
4. Enter property details and compute VAT: Sale Price × 5%
5. Upload required documents and submit payment

**Documents Required:**
- Sale / Transfer Agreement (SPA)
- Title Deed or Oqood certificate
- Emirates ID / Passport (seller)
- Copy of FTA notice
- VAT calculation worksheet

**Legal Reference:** Federal Decree-Law No. 8 of 2017, Article 36 (Supply of Real Estate); Cabinet Decision No. 52 of 2017, Schedule 3 (commercial property at standard rate).
```

---

## Fix 3a — Source Scoping (Analyst Sources in Legal Studio)

### Root cause

`LegalStudio.tsx` `sendMessage` function builds the request body without including `selected_doc_ids`. The backend `ChatRequest` model accepts `selected_doc_ids` and uses it to scope the RAG filter, but it never receives a value from the frontend.

### Fix

In `LegalStudio.tsx`, add `selected_doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined` to the request body sent to `/api/chat/send`.

---

## Fix 3b — Fast Mode First-Message Timeout

### Root cause

In `fast` mode, the backend runs three sequential/parallel LLM calls (domain classifier, intent classifier, query variations) **before** the `StreamingResponse` generator starts yielding any bytes. With a remote LLM provider these can take 10-20 s each, easily exceeding the 30 s frontend timeout.

### Fix — two-part

**Backend (`backend/api/chat.py`):** Move domain classification, intent classification, and query variations **inside** the `generate()` async generator (streaming path only). DB operations (conversation creation, message save, memory load) remain outside the generator since they must complete before the HTTP response starts. Yield the `meta` event as soon as domain classification is done (not waiting for intent or query variations). This means the client gets the first byte within ~2-3 s.

Structure inside `generate()`:
```
1. classify_domain → yield meta event immediately
2. classify_intent (parallel with step 3)
3. _get_query_variations (parallel with step 2)
4. await both → build system_prompt + run RAG searches
5. stream LLM response
```

**Frontend (`LegalStudio.tsx`):** Increase the abort timeout from `30_000` ms to `90_000` ms (90 s). This covers slow cold-start LLM providers while still preventing truly stuck requests.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/api/chat.py` | Add `_generate_title()` background task; restructure `generate()` to yield meta event early |
| `backend/core/prompt_router.py` | Extend VAT system prompt with commercial property section + few-shot example |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Add `selected_doc_ids` to chat request body; increase timeout to 90 s |

---

## Error Handling

- Title generation failure is non-fatal — conversation keeps the 80-char truncated title.
- Domain/intent classifier errors inside `generate()` fall back to `GENERAL_LAW` + generic intent (same as before).
- RAG filter fallback (no results → retry without filter) is preserved.

---

## Testing Checklist

- [ ] Home page shows AI-generated 6-8 word title after sending first message
- [ ] VAT query "Hotel Apartment sale + FTA notice" returns correct one-pager with portal steps and documents
- [ ] Legal Studio only surfaces documents from `selectedDocIds`, not Analyst documents
- [ ] First message in Fast mode gets a response within 90 s with no double-send required
- [ ] All existing chat functionality (streaming, sources, deep research, analyst mode) continues to work
