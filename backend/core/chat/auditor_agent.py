"""Auditor agent for analyzing documents for risks and compliance gaps."""
import json
import logging
from typing import Optional
from pydantic import BaseModel
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine

logger = logging.getLogger(__name__)


class AuditFinding(BaseModel):
    severity: str  # "low" | "medium" | "high"
    document: str
    finding: str


class AuditResult(BaseModel):
    risk_flags: list[AuditFinding]
    anomalies: list[AuditFinding]
    compliance_gaps: list[AuditFinding]
    summary: str


async def _analyze_documents(document_ids: list[str]) -> AuditResult:
    """Analyze documents using LLM for risk flags, anomalies, and compliance gaps."""
    # Gather context from each document via RAG
    context_parts = []
    for doc_id in document_ids:
        try:
            results = await rag_engine.search(
                f"audit risk compliance anomaly",
                top_k=5,
                filter={"doc_id": doc_id} if doc_id else None,
            )
            for r in results:
                context_parts.append(f"[Doc {doc_id}]: {r['text'][:500]}")
        except Exception as e:
            logger.warning(f"RAG search failed for doc {doc_id}: {e}")

    if not context_parts:
        return AuditResult(
            risk_flags=[],
            anomalies=[],
            compliance_gaps=[],
            summary="No content could be retrieved from the selected documents.",
        )

    context = "\n\n".join(context_parts)

    system = (
        "You are a UAE audit and compliance specialist. Analyze the following document excerpts "
        "and identify: (1) risk flags, (2) anomalies, (3) compliance gaps.\n"
        "Respond ONLY with JSON:\n"
        '{"risk_flags": [{"severity": "high|medium|low", "document": "doc_id", "finding": "..."}], '
        '"anomalies": [...same shape...], '
        '"compliance_gaps": [...same shape...], '
        '"summary": "overall summary"}'
    )

    llm = get_llm_provider()
    resp = await llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": context},
        ],
        temperature=0.2,
        max_tokens=2000,
    )

    try:
        raw = resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        data = json.loads(raw)
        return AuditResult(
            risk_flags=[AuditFinding(**f) for f in data.get("risk_flags", [])],
            anomalies=[AuditFinding(**f) for f in data.get("anomalies", [])],
            compliance_gaps=[AuditFinding(**f) for f in data.get("compliance_gaps", [])],
            summary=data.get("summary", ""),
        )
    except Exception as e:
        logger.warning("Audit analysis parse failed: %s", e)
        return AuditResult(
            risk_flags=[],
            anomalies=[],
            compliance_gaps=[],
            summary="Analysis could not be completed.",
        )


async def run_audit(document_ids: list[str]) -> dict:
    """Run audit analysis on selected documents. Returns dict suitable for JSON response."""
    if not document_ids:
        return {
            "risk_flags": [],
            "anomalies": [],
            "compliance_gaps": [],
            "summary": "No documents selected.",
        }
    result = await _analyze_documents(document_ids)
    return result.model_dump()
