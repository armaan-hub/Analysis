"""
Financial Audit Council Multi-Agent Orchestrator.

Orchestrates the 6-agent Financial Audit Council to process:
- Document 1: Balance Sheet / Trial Balance
- Document 2: Profit & Loss Statement
- Document 3: Trade License & Memorandum of Association (MOA)
- Document 4: Comparative Mainland Audit Report Target Template

Enforces:
1. Strict Chronological Presentation: 2025 first, 2024 second.
2. Complete Corporate Context Integration from Trade License & MOA.
3. Audit-Grade Formatting: Clean Markdown tables, bold totals, indented sub-accounts, '-' zero notation.
4. Meticulous Financial Mapping into target Comparative Mainland structure.
5. Mathematical Verification & Discrepancy Flagging at the end.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from core.council.audit_council_personas import (
    AUDIT_COUNCIL_AGENTS,
    AuditSubAgent,
)
from core.council.comparative_mainland_template import (
    COLUMN_ORDER,
    STANDARD_NOTES_SPEC,
    TEMPLATE_CURRENCY,
    TEMPLATE_ID,
    TEMPLATE_NAME,
    YEAR_COMPARATIVE,
    YEAR_CURRENT,
)

logger = logging.getLogger(__name__)


def _build_agent_prompt(
    agent: AuditSubAgent,
    *,
    doc1_balance_sheet: str,
    doc2_profit_loss: str,
    doc3_corporate_legal: str,
    doc4_template_notes: str,
    prior_stage_results: list[tuple[str, str, str]],
) -> str:
    """Build specific prompt for each subagent in the council pipeline."""
    prior_context = "\n\n".join(
        f"### {agent_name} ({agent_role}) Findings:\n{content}"
        for agent_name, agent_role, content in prior_stage_results
    ) or "(No prior subagent findings yet - initial stage)"

    template_guidance = (
        f"TARGET TEMPLATE SPECIFICATION (Document 4 - {TEMPLATE_NAME}):\n"
        f"- Target Currency: {TEMPLATE_CURRENCY}\n"
        f"- Current Year (Column 1): {YEAR_CURRENT}\n"
        f"- Comparative Year (Column 2): {YEAR_COMPARATIVE}\n"
        f"- Column Ordering: {COLUMN_ORDER[0]} (left / first), {COLUMN_ORDER[1]} (right / second)\n"
        f"- Zero / Nil Value Rule: Always use '-' for zero balances\n"
        f"- Required Note Disclosures: Notes 1 to 15 (Corporate info, IFRS policies, PPE, ROU, Receivables, Cash, Share Capital, Tax, etc.)\n"
    )

    return (
        f"{agent.system_prompt}\n\n"
        f"=== TARGET SPECIFICATION & RULES ===\n"
        f"{template_guidance}\n\n"
        f"=== INPUT DOCUMENT 1: BALANCE SHEET & TRIAL BALANCE ===\n"
        f"{doc1_balance_sheet or '[No Balance Sheet / TB provided]'}\n\n"
        f"=== INPUT DOCUMENT 2: PROFIT & LOSS STATEMENT ===\n"
        f"{doc2_profit_loss or '[No Profit & Loss provided]'}\n\n"
        f"=== INPUT DOCUMENT 3: TRADE LICENSE & MOA ===\n"
        f"{doc3_corporate_legal or '[No Trade License / MOA provided]'}\n\n"
        f"=== ADDITIONAL TEMPLATE NOTES & CONTEXT ===\n"
        f"{doc4_template_notes or '[Standard Comparative Mainland Template rules apply]'}\n\n"
        f"=== PRIOR COUNCIL SUBAGENT FINDINGS ===\n"
        f"{prior_context}\n\n"
        f"Execute your assigned role '{agent.name}' now. Output with extreme technical precision."
    )


async def run_financial_audit_council_stream(
    *,
    doc1_balance_sheet: str,
    doc2_profit_loss: str,
    doc3_corporate_legal: str,
    doc4_template_notes: str = "",
    llm: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Stream real-time multi-agent deliberation events across all 6 financial audit council agents.
    Yields JSON-serializable event dicts.
    """
    error: str | None = None
    prior_stage_results: list[tuple[str, str, str]] = []
    current_stage = "init"

    try:
        total_agents = len(AUDIT_COUNCIL_AGENTS)
        for idx, agent in enumerate(AUDIT_COUNCIL_AGENTS, start=1):
            current_stage = agent.stage
            yield {
                "type": "audit_council_agent_start",
                "agent": agent.name,
                "role": agent.role,
                "stage": agent.stage,
                "step": idx,
                "total_steps": total_agents,
                "status": "in_progress",
            }

            prompt = _build_agent_prompt(
                agent,
                doc1_balance_sheet=doc1_balance_sheet,
                doc2_profit_loss=doc2_profit_loss,
                doc3_corporate_legal=doc3_corporate_legal,
                doc4_template_notes=doc4_template_notes,
                prior_stage_results=prior_stage_results,
            )

            buf: list[str] = []
            max_tokens = 3000 if agent.stage in ("report_synthesis", "mainland_mapping") else 2000
            temp = 0.15 if agent.stage in ("math_qc", "tb_audit") else 0.25

            try:
                async for piece in llm.chat_stream(
                    [{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temp,
                ):
                    buf.append(piece)
                    yield {
                        "type": "audit_council_delta",
                        "agent": agent.name,
                        "stage": agent.stage,
                        "delta": piece,
                    }
            except Exception as exc:
                logger.exception("Error during audit subagent streaming: %s", agent.name)
                partial_output = "".join(buf)
                if partial_output:
                    yield {
                        "type": "audit_council_agent_complete",
                        "agent": agent.name,
                        "stage": agent.stage,
                        "content": partial_output,
                        "truncated": True,
                    }
                error = f"{type(exc).__name__}: {exc}"
                yield {
                    "type": "audit_council_error",
                    "error": error,
                    "agent": agent.name,
                    "stage": current_stage,
                }
                break

            full_content = "".join(buf)
            yield {
                "type": "audit_council_agent_complete",
                "agent": agent.name,
                "stage": agent.stage,
                "content": full_content,
                "step": idx,
                "total_steps": total_agents,
            }
            prior_stage_results.append((agent.name, agent.role, full_content))

    except GeneratorExit:
        return
    except Exception as exc:
        logger.exception("Fatal error in financial audit council pipeline")
        error = f"{type(exc).__name__}: {exc}"
        yield {"type": "audit_council_error", "error": error, "stage": current_stage}

    done_payload: dict[str, Any] = {
        "type": "audit_council_done",
        "stages_completed": len(prior_stage_results),
        "total_stages": len(AUDIT_COUNCIL_AGENTS),
    }
    if error:
        done_payload["error"] = error
    yield done_payload


async def run_financial_audit_council(
    *,
    doc1_balance_sheet: str,
    doc2_profit_loss: str,
    doc3_corporate_legal: str,
    doc4_template_notes: str = "",
    llm: Any,
) -> dict[str, Any]:
    """Non-streaming execution of the full 6-agent Financial Audit Council."""
    stage_outputs: dict[str, str] = {}
    last_error: str | None = None

    async for evt in run_financial_audit_council_stream(
        doc1_balance_sheet=doc1_balance_sheet,
        doc2_profit_loss=doc2_profit_loss,
        doc3_corporate_legal=doc3_corporate_legal,
        doc4_template_notes=doc4_template_notes,
        llm=llm,
    ):
        if evt.get("type") == "audit_council_agent_complete":
            stage = evt.get("stage", "unknown")
            stage_outputs[stage] = evt.get("content", "")
        elif evt.get("type") == "audit_council_error":
            last_error = evt.get("error")

    report_markdown = stage_outputs.get("report_synthesis", "")
    qc_critique = stage_outputs.get("math_qc", "")

    return {
        "success": last_error is None and bool(report_markdown),
        "report_markdown": report_markdown,
        "qc_critique": qc_critique,
        "stage_outputs": stage_outputs,
        "error": last_error,
        "template_id": TEMPLATE_ID,
        "template_name": TEMPLATE_NAME,
        "year_order": COLUMN_ORDER,
    }
