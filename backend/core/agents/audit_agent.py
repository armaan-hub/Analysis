"""
Audit Agent — generates clarification questions based on TB risk flags
and produces the final audit report using the LLM.
"""
from __future__ import annotations

import logging
from typing import Any

from core.agents.base_agent import BaseAgent
from core.agents.trial_balance_classifier import classify_risks, get_risk_summary
from core.agents.trial_balance_classifier import group_tb_for_ifrs, format_ifrs_for_llm
from core.llm_manager import get_llm_provider
from config import settings

logger = logging.getLogger(__name__)


class AuditAgent(BaseAgent):
    """Agent responsible for audit report generation."""

    async def ask_questions(self, tb_data: list[dict]) -> list[dict]:
        """
        Generate CA-style clarification questions based on risk-flagged TB rows.

        Returns at most 8 questions focused on high/medium risk items.
        """
        classified = classify_risks(tb_data)
        questions: list[dict] = []

        for row in classified:
            if row["risk"] not in ("high", "medium"):
                continue
            account = row.get("account", "Unknown Account")
            category = row.get("mappedTo", "")
            risk = row["risk"]

            # Generate a question tailored to the account category
            cat_lc = category.lower()
            if "cash" in cat_lc or "bank" in cat_lc:
                q_text = f"Has a bank confirmation letter been obtained for '{account}'? (ISA 505)"
            elif "receivable" in cat_lc or "debtor" in cat_lc:
                q_text = f"Has debtor circularisation been performed for '{account}'?"
            elif "revenue" in cat_lc or "sales" in cat_lc or "income" in cat_lc:
                q_text = f"Is revenue from '{account}' recognised per IFRS 15 — point-in-time or over time?"
            elif "retained" in cat_lc or "equity" in cat_lc:
                q_text = f"Has the movement in '{account}' been reconciled to board-approved dividends/distributions?"
            elif "related party" in cat_lc or "director" in cat_lc or "shareholder" in cat_lc:
                q_text = f"Is the related-party transaction '{account}' disclosed under IAS 24?"
            else:
                q_text = f"Can you provide supporting documentation for '{account}' ({category})?"

            questions.append({
                "id": f"ca_{len(questions)}",
                "question": q_text,
                "account": account,
                "risk": risk,
            })

            if len(questions) >= 8:
                break

        return questions

    async def generate(self, tb_data: list[dict], answers: dict[str, str], **kwargs) -> str:
        """
        Generate an audit report using the LLM.

        Kwargs:
            opinion (str): "unqualified" | "qualified" | "disclaimer" | "adverse"
            disclaimer_text (str): Auditor's opinion summary text.
            tb_data (list[dict]): Trial balance rows (also passed as positional arg).
            report_fields (dict): Additional report metadata fields.
            company_info (dict | None): Company details.
            audit_format (str): Report style, e.g. "big4".
            prior_year_content (str): Prior year narrative or data.
        """
        opinion: str = kwargs.get("opinion", "unqualified")
        disclaimer_text: str = kwargs.get("disclaimer_text", "")
        report_fields: dict = kwargs.get("report_fields", {})
        company_info: dict | None = kwargs.get("company_info", None)
        prior_year_content: str = kwargs.get("prior_year_content", "")

        # Opinion gate
        if opinion == "adverse":
            raise ValueError(
                "Adverse opinion: cannot generate a standard audit report. "
                "Manual preparation required. Review ISA 705.8."
            )

        opinion_prefix = {
            "qualified": (
                "IMPORTANT: The auditor's opinion is QUALIFIED (ISA 705.7 — Except For). "
                "Your report MUST include a 'Basis for Qualified Opinion' section and the "
                "qualified opinion paragraph. "
            ),
            "disclaimer": (
                "IMPORTANT: The auditor's opinion is a DISCLAIMER OF OPINION (ISA 705.9). "
                "Your report MUST include a 'Basis for Disclaimer of Opinion' section. "
                "The auditor cannot form an opinion. "
            ),
        }.get(opinion, "")

        base_prompt = (
            "You are a senior UAE-qualified auditor. Generate a professional audit report in Markdown. "
            "Include: Audit Opinion, Basis of Opinion, Key Audit Matters, Responsibilities of Management, "
            "Auditor's Responsibilities, and a Management Letter summary. "
            "Reference IFRS and UAE Federal Law No. 2 of 2015 where appropriate."
        )
        system_prompt = opinion_prefix + base_prompt

        context_lines: list[str] = []
        if company_info:
            for k, v in company_info.items():
                if v:
                    context_lines.append(f"**{k.replace('_', ' ').title()}**: {v}")
        for k, v in report_fields.items():
            if v:
                context_lines.append(f"**{k.replace('_', ' ').title()}**: {v}")
        if disclaimer_text:
            context_lines.append(f"\n**Auditor's Opinion Summary**: {disclaimer_text}")
        if prior_year_content:
            context_lines.append(f"\n**Prior Year Data Available**: Yes")
        if tb_data:
            # Group TB data using IFRS classification
            grouped = group_tb_for_ifrs(tb_data)
            if any(grouped.get(k, {}).get("rows") for k in grouped if k != "_totals"):
                ifrs_context = format_ifrs_for_llm(grouped)
                context_lines.append("\n" + ifrs_context)
            else:
                # Fallback to flat table if classification failed
                context_lines.append("\n**Trial Balance Summary:**")
                context_lines.append("| Account | Category | Amount (AED) |")
                context_lines.append("|---------|----------|-------------|")
                for row in tb_data[:30]:
                    context_lines.append(
                        f"| {row.get('account', '')} | {row.get('mappedTo', '')} | "
                        f"{float(row.get('amount', 0)):,.2f} |"
                    )

        user_prompt = "Generate the audit report for the following engagement data:\n\n" + "\n".join(context_lines)

        llm = get_llm_provider(None)
        response = await llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=settings.max_tokens,
        )
        return response.content
