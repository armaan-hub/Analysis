# SSE Error-Handling Bug Fix — LegalStudio

**Date:** 2026-05-08  
**Topic:** Fix "No response received" overriding specific SSE error messages  
**Status:** Approved  
**Scope:** Frontend only — `LegalStudio.tsx`

---

## Problem

When the backend streams an `error` SSE event (e.g., NVIDIA NIM degraded, timeout, network failure), the frontend shows the generic **"⚠️ No response received. Please try again."** message instead of the specific, actionable error text.

### Root Cause

`sendMessage` in `LegalStudio.tsx` has two error paths that conflict:

**Path 1 — SSE error event handler** (inside the SSE loop):
```ts
} else if (evt.type === 'error') {
  const errMsg = evt.message ?? 'The AI encountered an error. Please try again.';
  setMessages(prev => {
    const copy = prev.filter(m => m.id !== aiMsgId);  // removes original placeholder
    return [...copy, { id: crypto.randomUUID(), text: `⚠️ ${errMsg}`, ... }];  // NEW UUID
  });
}
```

**Path 2 — Post-stream guard** (after the SSE loop ends):
```ts
if (!aiText) {
  setMessages(prev => {
    const hasFilled = prev.find(m => m.id === aiMsgId && 'text' in m && m.text);
    if (hasFilled) return prev;  // guard never fires — aiMsgId was replaced with new UUID above
    const copy = prev.filter(m => m.id !== aiMsgId);  // no-op
    return [...copy, { text: '⚠️ No response received. Please try again.', ... }];  // appended
  });
}
```

Because the error handler replaced `aiMsgId` with a new UUID, the `hasFilled` guard can never find it. The post-stream block runs unconditionally when `aiText` is empty, appending a second error message and obscuring the specific one.

### Affected File

- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

### Affected Scenarios

| Scenario | Before Fix | After Fix |
|---|---|---|
| NVIDIA NIM degraded | "No response received" | "The AI model is temporarily unavailable (service degraded). Please try again in a few minutes." |
| Network timeout | "No response received" | "Connection to AI service timed out. Please check your network and try again." |
| Rate limit | "No response received" | "AI API rate limit reached. Please wait a moment and try again." |
| Complete stream failure (no events) | "No response received" | "No response received" ✅ (correct — no better info available) |

---

## Solution

**Option A — `hasError` flag** (chosen)

Add a `hasError` boolean flag to track whether an error SSE event was already handled. This prevents the post-stream generic message from running when a specific error message was already shown.

### Changes

**File**: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

**Change 1** — Declare flag alongside `aiText`:
```ts
// Before
let aiText = '';

// After
let aiText = '';
let hasError = false;
```

**Change 2** — Set flag in error event handler:
```ts
// Before
} else if (evt.type === 'error') {
  const errMsg = evt.message ?? '...';

// After
} else if (evt.type === 'error') {
  hasError = true;
  const errMsg = evt.message ?? '...';
```

**Change 3** — Guard post-stream check:
```ts
// Before
if (!aiText) {

// After
if (!aiText && !hasError) {
```

### Why Not Option B (set `aiText` to error string)?

`aiText` is passed to `setLastAnswer(aiText)` after the stream. If `aiText` holds the error message, `lastAnswer` would be set to error text, which is used downstream for report generation. Semantically wrong.

### Why Not Option C (fix `hasFilled` check)?

The existing `hasFilled` logic is fragile (looks up by ID). Rather than fix a broken guard, we eliminate the need for it with a clean flag.

---

## Out of Scope

- Retry button / automatic retry logic (future enhancement)
- Model health status indicator (future enhancement)
- Web search fallback when LLM fails (future enhancement)
- Applying same fix to other chat components (not exhibiting same bug)

---

## Testing

Manual test plan:
1. Start backend with a bad/expired NVIDIA API key → send a chat message in LegalStudio → verify the specific auth error message appears, not "No response received"
2. Disconnect network during a chat → verify timeout message appears
3. Normal successful chat → verify response still streams correctly

No automated frontend tests for this path currently exist.

---

## Implementation

3-line change in `LegalStudio.tsx`. No backend changes. No new dependencies.
