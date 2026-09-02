"""
Financial Audit Council CLI (Standalone Local Executable).

Runs the 6-Subagent Financial Audit Council locally from terminal.
Supports real-time streaming, sample data execution, OpenCode Zen free tier,
local LLM proxies, and full markdown report output.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

from .llm import (
    DEFAULT_OPENCODE_BASE_URL,
    DEFAULT_OPENCODE_KEY,
    DEFAULT_OPENCODE_MODEL,
    get_llm_client,
)
from .orchestrator import run_financial_audit_council_stream
from .personas import AUDIT_COUNCIL_AGENTS

# ANSI Color formatting
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_RED = "\033[31m"

AGENT_ICONS = {
    "legal_extraction": "⚖️ ",
    "tb_audit": "📊",
    "pl_analysis": "📈",
    "mainland_mapping": "📑",
    "report_synthesis": "🖋️ ",
    "math_qc": "🔍",
}


def _print_banner():
    print(f"\n{C_BOLD}{C_CYAN}╔════════════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║     6-SUBAGENT FINANCIAL AUDIT COUNCIL (STANDALONE LOCAL RUNNER)           ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║     Statutory UAE Comparative Mainland Audit & Financial Mapping Engine    ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚════════════════════════════════════════════════════════════════════════════╝{C_RESET}\n")


def _read_file_safe(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p.resolve()}")
    return p.read_text(encoding="utf-8")


def _get_sample_dir() -> Path:
    return Path(__file__).parent / "sample_data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="6-Subagent Financial Audit Council - Standalone Local CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Document Inputs
    parser.add_argument("--doc1", type=str, help="Path to Document 1 (Balance Sheet / Trial Balance)")
    parser.add_argument("--doc2", type=str, help="Path to Document 2 (Profit & Loss Statement)")
    parser.add_argument("--doc3", type=str, help="Path to Document 3 (Trade License & MOA)")
    parser.add_argument("--doc4", type=str, default="", help="Path to Document 4 (Template notes / context)")
    parser.add_argument("--sample", action="store_true", help="Run with built-in sample data (Al Khaleej Engineering LLC)")

    # Output
    parser.add_argument("-o", "--output", type=str, default="audit_report_output.md", help="Path to save synthesized audit report")

    # LLM Provider Configuration
    parser.add_argument("--provider", type=str, default="opencode", choices=["opencode", "openai", "proxy", "anthropic"], help="LLM Provider")
    parser.add_argument("--model", type=str, default=DEFAULT_OPENCODE_MODEL, help=f"Model ID (default: {DEFAULT_OPENCODE_MODEL})")
    parser.add_argument("--api-key", type=str, default=None, help="Provider API Key (defaults to embedded OpenCode key or ENV)")
    parser.add_argument("--base-url", type=str, default=None, help="Custom Base URL (e.g. http://127.0.0.1:4001/v1)")

    # Execution controls
    parser.add_argument("--no-stream", action="store_true", help="Disable live token streaming to terminal")

    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()

    _print_banner()

    # Load Documents
    sample_dir = _get_sample_dir()
    if args.sample or (not args.doc1 and not args.doc2 and not args.doc3):
        print(f"{C_YELLOW}⚡ Using built-in sample data from {sample_dir.resolve()}{C_RESET}")
        doc1_path = sample_dir / "doc1_balance_sheet_trial_balance.txt"
        doc2_path = sample_dir / "doc2_profit_loss.txt"
        doc3_path = sample_dir / "doc3_trade_license_and_moa.txt"
        doc4_path = sample_dir / "doc4_target_template_spec.txt"

        doc1 = _read_file_safe(doc1_path)
        doc2 = _read_file_safe(doc2_path)
        doc3 = _read_file_safe(doc3_path)
        doc4 = _read_file_safe(doc4_path) if doc4_path.exists() else ""
    else:
        if not args.doc1 or not args.doc2 or not args.doc3:
            print(f"{C_RED}Error: Please specify --doc1, --doc2, and --doc3 or use --sample{C_RESET}", file=sys.stderr)
            return 1
        print(f"{C_CYAN}Loading input documents...{C_RESET}")
        doc1 = _read_file_safe(args.doc1)
        doc2 = _read_file_safe(args.doc2)
        doc3 = _read_file_safe(args.doc3)
        doc4 = _read_file_safe(args.doc4) if args.doc4 else ""

    # Initialize LLM
    print(f"\n{C_BOLD}Configuration:{C_RESET}")
    print(f"  Provider: {C_GREEN}{args.provider}{C_RESET}")
    print(f"  Model:    {C_GREEN}{args.model}{C_RESET}")
    print(f"  Output:   {C_GREEN}{args.output}{C_RESET}")
    if args.base_url:
        print(f"  Base URL: {C_GREEN}{args.base_url}{C_RESET}")

    llm = get_llm_client(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )

    print(f"\n{C_BOLD}{C_MAGENTA}🚀 Launching 6-Subagent Council Pipeline...{C_RESET}\n")

    stage_outputs: dict[str, str] = {}
    current_agent_name = ""
    start_time = time.time()

    async for evt in run_financial_audit_council_stream(
        doc1_balance_sheet=doc1,
        doc2_profit_loss=doc2,
        doc3_corporate_legal=doc3,
        doc4_template_notes=doc4,
        llm=llm,
    ):
        evt_type = evt.get("type")

        if evt_type == "audit_council_agent_start":
            current_agent_name = evt.get("agent", "")
            step = evt.get("step", 1)
            total = evt.get("total_steps", 6)
            role = evt.get("role", "")
            icon = AGENT_ICONS.get(evt.get("stage", ""), "🤖")
            print(f"\n{C_BOLD}{C_CYAN}────────────────────────────────────────────────────────────────────────{C_RESET}")
            print(f"{C_BOLD}{icon} [Stage {step}/{total}] {current_agent_name} ({role}){C_RESET}")
            print(f"{C_BOLD}{C_CYAN}────────────────────────────────────────────────────────────────────────{C_RESET}\n")

        elif evt_type == "audit_council_delta":
            if not args.no_stream:
                sys.stdout.write(evt.get("delta", ""))
                sys.stdout.flush()

        elif evt_type == "audit_council_agent_complete":
            stage = evt.get("stage", "")
            content = evt.get("content", "")
            stage_outputs[stage] = content
            if args.no_stream:
                print(content)
            print(f"\n\n{C_GREEN}✓ Stage '{current_agent_name}' finished successfully.{C_RESET}\n")

        elif evt_type == "audit_council_error":
            err_msg = evt.get("error", "Unknown error")
            print(f"\n{C_RED}❌ Error in agent '{evt.get('agent', '')}': {err_msg}{C_RESET}\n", file=sys.stderr)

        elif evt_type == "audit_council_done":
            completed = evt.get("stages_completed", 0)
            total = evt.get("total_stages", 6)
            elapsed = time.time() - start_time
            print(f"\n{C_BOLD}{C_GREEN}════════════════════════════════════════════════════════════════════════════{C_RESET}")
            print(f"{C_BOLD}{C_GREEN}🎉 AUDIT COUNCIL COMPLETE ({completed}/{total} stages finished in {elapsed:.1f}s){C_RESET}")
            print(f"{C_BOLD}{C_GREEN}════════════════════════════════════════════════════════════════════════════{C_RESET}\n")

    # Save Output
    report_markdown = stage_outputs.get("report_synthesis", "")
    qc_critique = stage_outputs.get("math_qc", "")

    full_output_doc = []
    if report_markdown:
        full_output_doc.append(report_markdown)
    if qc_critique:
        full_output_doc.append("\n\n---\n\n## STAGE 6: AUDIT MATHEMATICAL VERIFICATION & QUALITY CONTROL\n\n" + qc_critique)

    if full_output_doc:
        out_path = Path(args.output)
        out_path.write_text("\n".join(full_output_doc), encoding="utf-8")
        print(f"{C_BOLD}📁 Final Report saved to: {C_GREEN}{out_path.resolve()}{C_RESET}\n")
    else:
        print(f"{C_RED}Warning: No synthesized report output was captured.{C_RESET}\n", file=sys.stderr)

    return 0


def main():
    try:
        sys.exit(asyncio.run(main_async()))
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Execution cancelled by user.{C_RESET}")
        sys.exit(130)


if __name__ == "__main__":
    main()
