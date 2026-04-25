# Design: Fix AI-Generated Title Race Condition

**Date:** 2026-04-24  
**Status:** Proposed  
**Author:** Gemini CLI

## Problem Statement

In `backend/api/chat.py`, the `_generate_title` background task is scheduled using `asyncio.create_task` immediately before the main endpoint returns. Because the database session (provided by `get_db`) only commits *after* the endpoint function returns, there is a race condition where `_generate_title` may attempt to fetch the new `Conversation` row before it has been committed.

This results in "Conversation not found" or "Title generation failed" warnings, and the conversation retains its truncated raw question title instead of a polished AI summary.

## Proposed Fix

### 1. Switch to `BackgroundTasks`

FastAPI's `BackgroundTasks` are specifically designed to run *after* the response has been sent. This ensures that the dependency cleanup (including the `session.commit()` in `get_db`) has completed before the task begins.

**In `backend/api/chat.py`:**
- Replace `asyncio.create_task(_generate_title(...))` with `background_tasks.add_task(_generate_title, ...)` in the non-streaming path.
- In the streaming path (inside the `generate()` generator), `db.commit()` is called explicitly. Scheduling via `background_tasks.add_task` is still preferred for consistency and to avoid keeping the connection open longer than needed.

### 2. Add Defensive Retry/Delay (Optional but Recommended)

Even with `BackgroundTasks`, in high-concurrency environments or with slow disk I/O (SQLite), a tiny 0.1s delay or a single retry in `_generate_title` adds robustness.

## implementation Details

### `backend/api/chat.py`

**Non-streaming path:**
```python
    if _title_args:
        background_tasks.add_task(_generate_title, *_title_args)
```

**Streaming path (`generate()`):**
```python
                await db.commit()
                # ...
                if _title_args:
                    background_tasks.add_task(_generate_title, *_title_args)
```

**Note:** The `generate()` function already has access to the `background_tasks` object from the outer `send_message` scope.

## Verification Plan

1. **Reproduction Test:** Create a test that mock-delays the DB commit and asserts that `_generate_title` fails with the current implementation but succeeds with `BackgroundTasks`.
2. **Integration Test:** Verify that first messages consistently get AI-generated titles on the Home Page after a single refresh.
