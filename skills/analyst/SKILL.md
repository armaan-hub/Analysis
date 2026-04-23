---
name: analyst
description: Use when the user wants a structured financial / audit report — MIS pack, audit findings, KPI dashboard, ratio analysis, variance analysis. Requires uploaded documents (financials, ledgers, schedules).
---

# Analyst Skill

## When to Use
- "Generate an audit report", "produce MIS", "do ratio analysis", "compare years"
- User has uploaded financial documents (PDF/XLSX) into the notebook

## When NOT to Use
- General Q&A (Fast mode); investigation-style research (Deep Research)

## Prerequisites
- At least 1 document uploaded and indexed
- Conversation mode set to `analyst`

## Workflow
1. Set `mode = 'analyst'` (mounts ThreePaneLayout: Sources | Chat | Artifact).
2. Use `POST /api/chat/send` with `mode='analyst'` — backend uses the `analyst` system prompt (CA-style auditor persona).
3. The Artifact panel auto-detects report metadata and offers `Generate Report`.
4. Stream report generation via `generateReportStreamUrl(...)`.
5. On completion, offer Markdown / DOCX / PDF downloads.

## Output Contract
- Report must include: Executive Summary → KPI Cards → Findings (with severity) → Recommendations → Appendix.
- Numbers traceable to source documents.

## Error Handling
- If ThreePaneLayout crashes, the AnalystErrorBoundary will display the error and offer "Reset Analyst" → switches back to Fast mode.
