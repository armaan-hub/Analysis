"""
Unit tests for the Standalone Local Financial Audit Council package.
Runs with zero external dependencies via pytest or standard python unittest.
"""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from typing import Any
from collections.abc import AsyncGenerator

from audit_council_local.personas import AUDIT_COUNCIL_AGENTS
from audit_council_local.template import (
    COLUMN_ORDER,
    TEMPLATE_CURRENCY,
    TEMPLATE_ID,
    YEAR_COMPARATIVE,
    YEAR_CURRENT,
    format_audit_currency,
)
from audit_council_local.llm import (
    DEFAULT_OPENCODE_MODEL,
    OPENCODE_FREE_MODELS,
    BaseLLMClient,
    get_llm_client,
)
from audit_council_local.orchestrator import run_financial_audit_council


class MockStreamingLLM(BaseLLMClient):
    """Mock LLM for testing orchestrator event pipeline without live network."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or [
            "Mock Legal Extraction completed.",
            "Mock Trial Balance Audit completed.",
            "Mock P&L Analysis completed.",
            "Mock Mainland Mapping completed.",
            "Mock Report Synthesis completed with SOFP, SOPL, Notes 1-29.",
            "Mock QC Verification passed with 0.00 variance.",
        ]
        self.call_count = 0

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        words = resp.split(" ")
        for w in words:
            yield w + " "
            await asyncio.sleep(0.001)


class TestLocalAuditCouncil(unittest.TestCase):
    """Test suite for standalone audit council."""

    def test_personas_and_council_structure(self):
        self.assertEqual(len(AUDIT_COUNCIL_AGENTS), 6)
        stages = [a.stage for a in AUDIT_COUNCIL_AGENTS]
        expected_stages = [
            "legal_extraction",
            "tb_audit",
            "pl_analysis",
            "mainland_mapping",
            "report_synthesis",
            "math_qc",
        ]
        self.assertEqual(stages, expected_stages)
        for agent in AUDIT_COUNCIL_AGENTS:
            self.assertTrue(len(agent.name) > 0)
            self.assertTrue(len(agent.system_prompt) > 50)

    def test_chronological_ordering_and_rules(self):
        self.assertEqual(list(COLUMN_ORDER), ["2025", "2024"])
        self.assertEqual(YEAR_CURRENT, "2025")
        self.assertEqual(YEAR_COMPARATIVE, "2024")
        self.assertEqual(TEMPLATE_CURRENCY, "AED")
        self.assertEqual(TEMPLATE_ID, "comparative-mainland")

    def test_audit_currency_formatting(self):
        self.assertEqual(format_audit_currency(0), "-")
        self.assertEqual(format_audit_currency("0.00"), "-")
        self.assertEqual(format_audit_currency(None), "-")
        self.assertEqual(format_audit_currency(1234567.89), "1,234,567.89")
        self.assertEqual(format_audit_currency(-50000.0), "(50,000.00)")

    def test_sample_documents_exist(self):
        sample_dir = Path(__file__).parent / "sample_data"
        doc1 = sample_dir / "doc1_balance_sheet_trial_balance.txt"
        doc2 = sample_dir / "doc2_profit_loss.txt"
        doc3 = sample_dir / "doc3_trade_license_and_moa.txt"
        doc4 = sample_dir / "doc4_target_template_spec.txt"

        self.assertTrue(doc1.exists(), "doc1 does not exist")
        self.assertTrue(doc2.exists(), "doc2 does not exist")
        self.assertTrue(doc3.exists(), "doc3 does not exist")
        self.assertTrue(doc4.exists(), "doc4 does not exist")

        self.assertIn("6,006,000.00", doc1.read_text(encoding="utf-8"))
        self.assertIn("9,250,000.00", doc2.read_text(encoding="utf-8"))
        self.assertIn("Al Khaleej Engineering & Trading L.L.C.", doc3.read_text(encoding="utf-8"))

    def test_llm_factory_and_free_tier(self):
        self.assertIn("laguna-s-2.1-free", OPENCODE_FREE_MODELS)
        self.assertIn("deepseek-v4-flash-free", OPENCODE_FREE_MODELS)
        client = get_llm_client("opencode")
        self.assertEqual(client.model, DEFAULT_OPENCODE_MODEL)

    def test_orchestrator_pipeline_mock_run(self):
        async def _run():
            mock_llm = MockStreamingLLM()
            res = await run_financial_audit_council(
                doc1_balance_sheet="Sample BS",
                doc2_profit_loss="Sample PL",
                doc3_corporate_legal="Sample Legal",
                doc4_template_notes="Sample Template",
                llm=mock_llm,
            )
            return res, mock_llm

        res, mock_llm = asyncio.run(_run())
        self.assertTrue(res["success"])
        self.assertEqual(mock_llm.call_count, 6)
        self.assertEqual(len(res["stage_outputs"]), 6)
        self.assertIn("report_synthesis", res["stage_outputs"])
        self.assertIn("math_qc", res["stage_outputs"])


if __name__ == "__main__":
    unittest.main()
