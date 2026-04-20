"""Auditor agent for analyzing documents for risks and compliance gaps."""
import json
import logging
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import select
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine
from db.database import async_session
from db.models import Document
from config import settings

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


FORMAT_INSTRUCTIONS = {
    "standard": "Present findings in Standard Audit format: Observation, Risk, Recommendation, Regulatory Reference.",
    "big4": "Present findings in Big 4 style with Executive Summary, Detailed Findings (each with Criteria, Condition, Cause, Effect, Recommendation), and Management Response sections.",
    "legal_brief": "Present findings as a Legal Brief: Issue, Legal Framework, Analysis, Opinion, and Next Steps.",
    "compliance": "Present findings as a Compliance Report: Compliance Status (Compliant / Partially Compliant / Non-Compliant), Regulatory Reference, Gap Description, Remediation Steps.",
}


async def _analyze_documents(
    document_ids: list[str],
    entity_name: str = "",
    period: str = "",
    format: str = "standard",
    scope: str = "Full financial audit",
) -> AuditResult:
    """Analyze documents using LLM for risk flags, anomalies, and compliance gaps."""
    # Resolve doc_id -> original_name from DB
    id_to_name: dict[str, str] = {}
    try:
        async with async_session() as session:
            rows = await session.execute(
                select(Document.id, Document.original_name).where(Document.id.in_(document_ids))
            )
            for row in rows:
                id_to_name[row.id] = row.original_name
    except Exception as e:
        logger.warning(f"Could not load document names from DB: {e}")

    # Gather context from each document via RAG
    context_parts = []
    for doc_id in document_ids:
        doc_name = id_to_name.get(doc_id, doc_id)
        try:
            results = await rag_engine.search(
                "audit risk compliance anomaly revenue expenses profit loss balance sheet trial balance cost of sales income tax",
                top_k=settings.top_k_results,
                filter={"doc_id": doc_id} if doc_id else None,
            )
            for r in results:
                context_parts.append(f"[Doc {doc_name}]: {r['text'][:500]}")
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
        '{"risk_flags": [{"severity": "high|medium|low", "document": "exact document name as provided", "finding": "..."}], '
        '"anomalies": [...same shape...], '
        '"compliance_gaps": [...same shape...], '
        '"summary": "overall summary"}\n'
        "In the document field, use the exact document name provided in the context."
    )

    context_block = ""
    if entity_name:
        context_block += f"\nEntity under audit: {entity_name}"
    if period:
        context_block += f"\nAudit period: {period}"
    if scope:
        context_block += f"\nScope: {scope}"
    format_instruction = FORMAT_INSTRUCTIONS.get(format, FORMAT_INSTRUCTIONS["standard"])
    if context_block:
        system += context_block
    system += f"\n{format_instruction}"

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


async def run_audit(
    document_ids: list[str],
    entity_name: str = "",
    period: str = "",
    format: str = "standard",
    scope: str = "Full financial audit",
) -> dict:
    """Run audit analysis on selected documents. Returns dict suitable for JSON response."""
    if not document_ids:
        return {
            "risk_flags": [],
            "anomalies": [],
            "compliance_gaps": [],
            "summary": "No documents selected.",
        }
    result = await _analyze_documents(
        document_ids,
        entity_name=entity_name,
        period=period,
        format=format,
        scope=scope,
    )
    return result.model_dump()
