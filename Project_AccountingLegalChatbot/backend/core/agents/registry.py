"""
Agent Registry — maps report_type keys to agent instances.

Each agent is a thin wrapper around a system prompt + LLM call.
The AuditAgent (in audit_agent.py) is registered separately as it has
richer logic (opinion gate, CA questions).
"""
from __future__ import annotations

import logging
from typing import Any

from core.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class _LLMReportAgent(BaseAgent):
    """Generic LLM-backed report agent. Subclasses set SYSTEM_PROMPT."""

    SYSTEM_PROMPT: str = ""

    async def ask_questions(self, tb_data: list[dict]) -> list[dict]:
        return []

    async def generate(self, tb_data: list[dict], answers: dict[str, str], **kwargs) -> str:
        from core.llm_manager import get_llm_provider
        from config import settings

        extra_fields: dict = kwargs.get("extra_fields", {})
        requirements: dict = kwargs.get("requirements", {})
        report_type: str = kwargs.get("report_type", "report")

        context_lines: list[str] = []
        for k, v in extra_fields.items():
            label = k.replace("_", " ").title()
            context_lines.append(f"**{label}**: {v}")

        if tb_data:
            context_lines.append("\n**Mapped Financial Data:**")
            context_lines.append("| Account | Mapped To | Amount (AED) |")
            context_lines.append("|---------|-----------|-------------|")
            for row in tb_data:
                account = row.get("account", row.get("account_name", ""))
                mapped_to = row.get("mapped_to", row.get("mappedTo", row.get("category", "")))
                amount = row.get("amount", row.get("net", 0))
                if isinstance(amount, (int, float)):
                    context_lines.append(f"| {account} | {mapped_to} | {amount:,.2f} |")
                else:
                    context_lines.append(f"| {account} | {mapped_to} | {amount} |")

        if requirements:
            context_lines.append("\n**Report Requirements (user-specified):**")
            for q, a in requirements.items():
                context_lines.append(f"- {q}: {a}")

        user_prompt = (
            f"Generate the {report_type.replace('_', ' ').title()} report for the following data:\n\n"
            + "\n".join(context_lines)
        )

        llm = get_llm_provider(None)
        response = await llm.chat(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=settings.max_tokens,
        )
        return response.content


class IFRSAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are an IFRS-qualified accountant. Generate IFRS Financial Statements in Markdown. "
        "Include: Statement of Financial Position, Statement of Profit or Loss and Other Comprehensive Income, "
        "Statement of Changes in Equity, Statement of Cash Flows (IAS 7 indirect method), and key accounting policy notes. "
        "Reference applicable IFRS standards (IFRS 15, IAS 16, IAS 36, IAS 38, etc.) where relevant."
    )


class VATAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a UAE VAT specialist. Generate a UAE VAT 201 Return analysis in Markdown. "
        "Apply Federal Decree-Law No. 8 of 2017. Include: Standard Rated Supplies, Zero Rated Supplies, "
        "Exempt Supplies, Output Tax, Standard Rated Purchases, Input Tax, per-Emirate breakdown (Box 1a–1g), "
        "Net VAT payable or recoverable, and any partial exemption or reverse charge notes."
    )


class CorporateTaxAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a UAE Corporate Tax specialist. Generate a detailed UAE Corporate Tax computation in Markdown. "
        "Apply Federal Decree-Law No. 47 of 2022. Include: Accounting Profit, Add-backs, "
        "Exempt Income, Taxable Income, Small Business Relief eligibility check (AED 3M threshold), "
        "9% tax rate calculation, and key notes on applicable exemptions."
    )


class ComplianceAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a UAE regulatory compliance expert. Generate a comprehensive compliance report in Markdown. "
        "Cover: VAT compliance, Corporate Tax registration, AML/CFT obligations, "
        "regulatory findings (if any), risk ratings (High/Medium/Low), and recommended remediation actions. "
        "Reference FTA regulations and UAE Federal laws."
    )


class MISAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a CFO-level management accountant. Generate a Management Information System (MIS) report in Markdown. "
        "Include: Executive Summary, Revenue vs Budget, Gross Margin Analysis, EBITDA, "
        "Key Performance Indicators (KPIs), Trend Analysis, and Management Commentary. "
        "Use tables where appropriate."
    )


class FinancialAnalysisAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a financial analyst. Generate a detailed financial analysis report in Markdown. "
        "Include: Liquidity Ratios (Current Ratio, Quick Ratio), Profitability Ratios (Gross Margin, Net Margin, ROE, ROA), "
        "Leverage Ratios (Debt-to-Equity, Interest Coverage), Efficiency Ratios, "
        "Trend Analysis, Benchmarking commentary, and an overall assessment."
    )


class BudgetAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a management accountant. Generate a Budget vs Actual Variance Analysis report in Markdown. "
        "Include: Revenue Variance (Favorable/Unfavorable), Expense Variance analysis, "
        "Overall Budget Performance, Variance explanations, and Recommendations for corrective action. "
        "Use tables to show Budget, Actual, Variance (AED and %) columns."
    )


class CashFlowAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are an IFRS-qualified accountant. Generate a Cash Flow Statement in Markdown following IFRS IAS 7. "
        "Include: Operating Activities (Indirect Method), Investing Activities, Financing Activities, "
        "Net Change in Cash, Opening and Closing Cash Balances, and Notes on significant non-cash transactions."
    )


class CustomReportAgent(_LLMReportAgent):
    SYSTEM_PROMPT = (
        "You are a professional financial analyst and accountant. Generate a comprehensive financial report in Markdown "
        "based on the provided data and any specific instructions given. Apply relevant UAE accounting standards, "
        "VAT laws, and IFRS where applicable. Structure the report clearly with sections and tables."
    )


# Lazy import AuditAgent to avoid circular deps at module load time
def _get_audit_agent() -> BaseAgent:
    from core.agents.audit_agent import AuditAgent
    return AuditAgent()


AGENT_REGISTRY: dict[str, BaseAgent] = {
    "ifrs": IFRSAgent(),
    "vat": VATAgent(),
    "corporate_tax": CorporateTaxAgent(),
    "corptax": CorporateTaxAgent(),   # alias
    "compliance": ComplianceAgent(),
    "mis": MISAgent(),
    "financial_analysis": FinancialAnalysisAgent(),
    "budget_vs_actual": BudgetAgent(),
    "budget": BudgetAgent(),          # alias
    "cash_flow": CashFlowAgent(),
    "custom": CustomReportAgent(),
}

# Audit agent registered separately (has opinion gate; lazy-loaded)
_AUDIT_AGENT_INSTANCE: BaseAgent | None = None


def get_agent(report_type: str) -> BaseAgent | None:
    """Return the registered agent for the given report type, or None."""
    global _AUDIT_AGENT_INSTANCE
    if report_type == "audit":
        if _AUDIT_AGENT_INSTANCE is None:
            _AUDIT_AGENT_INSTANCE = _get_audit_agent()
        return _AUDIT_AGENT_INSTANCE
    return AGENT_REGISTRY.get(report_type)
