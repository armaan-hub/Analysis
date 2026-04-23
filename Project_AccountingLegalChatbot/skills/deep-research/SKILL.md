---
name: deep-research
description: Use when user asks for a comprehensive multi-source investigation, a "research report", or anything requiring web + document synthesis with cited sources. Triggered by phrases like "research", "deep dive", "investigate", "comprehensive analysis".
---

# Deep Research Skill

## When to Use
- User explicitly says "research", "deep research", or asks for a "report"
- Question requires synthesizing multiple sources (web + uploaded docs)
- Output needs structured sections + downloadable PDF/DOCX

## When NOT to Use
- Simple factual question (use Fast mode)
- User wants a structured financial report (use Analyst mode)

## Workflow
1. Switch the chat mode to `deep_research` via `setMode('deep_research')` or send `mode=deep_research` in the API call.
2. Send the user's question via `POST /api/chat/research/start` (or via `useDeepResearch().run(query, docIds)`).
3. Stream events: `step`, `answer`, `done`. On `done.error`, show inline error.
4. Render the final answer in the Research Panel; offer Download PDF / Download DOCX.
5. Persist the answer to chat as a `research` message with sources.

## Output Contract
- Final document MUST include: Cover (query + date) → TOC → Body → Sources Appendix with clickable URLs.
- All factual claims cite an entry in Sources.

## Failure Modes
- Brave Search timeout → continue with doc-only synthesis.
- LLM stream failure → emit `done` with `error`; UI shows inline error.
