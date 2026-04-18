"""
CLI entry-point for learning an audit PDF template.

Runs TemplateAnalyzer and TemplateVerifier locally (sync), then optionally
saves / publishes the template via the REST API (requires running server).

Usage:
    cd backend
    python -m cli.template_learner --pdf path/to/file.pdf --name "My Template"
"""
import argparse
import json
import sys
import time
from pathlib import Path

from core.template_analyzer import TemplateAnalyzer
from core.template_verifier import TemplateVerifier

# ── Pretty-print helpers ──────────────────────────────────────────


def _print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def _print_config(config: dict) -> None:
    page = config.get("page", {})
    margins = config.get("margins", {})
    fonts = config.get("fonts", {})
    sections = config.get("sections", [])

    print(f"\n  Source:      {config.get('source', 'n/a')}")
    print(f"  Pages:       {config.get('page_count', 0)}")
    print(f"  Confidence:  {config.get('confidence', 0):.0%}")
    print(f"  Dimensions:  {page.get('width')} x {page.get('height')} {page.get('unit', 'pt')}")
    print(f"  Margins:     T={margins.get('top')}  B={margins.get('bottom')}  "
          f"L={margins.get('left')}  R={margins.get('right')}")

    for role in ("heading", "body", "footer"):
        f = fonts.get(role, {})
        print(f"  Font/{role:7s}: {f.get('family', '?')} @ {f.get('size', '?')}pt")

    if sections:
        print(f"\n  Sections ({len(sections)}):")
        for s in sections[:10]:
            print(f"    - {s.get('name', '?')} (page {s.get('page', '?')})")
        if len(sections) > 10:
            print(f"    ... and {len(sections) - 10} more")


def _print_report(report: dict) -> None:
    for check in report.get("checks", []):
        icon = "PASS" if check["passed"] else "FAIL"
        print(f"  [{icon}] {check['check']:20s}  conf={check['confidence']:.2f}  {check['message']}")
    print(f"\n  Overall: {report.get('summary', 'n/a')}  "
          f"(confidence {report.get('confidence', 0):.2f})")


# ── REST API helpers ──────────────────────────────────────────────


def _save_via_api(pdf_path: str, name: str, user_id: str, api_url: str) -> dict:
    """Upload the PDF to the running server and trigger learning."""
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        print("  ERROR: 'requests' package required for --save.  pip install requests", file=sys.stderr)
        sys.exit(1)

    # 1. Upload
    url = f"{api_url}/api/templates/upload-reference"
    with open(pdf_path, "rb") as fh:
        resp = requests.post(
            url,
            params={"name": name, "user_id": user_id},
            files={"file": (Path(pdf_path).name, fh, "application/pdf")},
        )
    if resp.status_code != 200:
        print(f"  Upload failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    job_id = resp.json()["job_id"]
    print(f"  Uploaded -> job {job_id}")

    # 2. Trigger learning
    resp = requests.post(f"{api_url}/api/templates/learn/{job_id}")
    if resp.status_code != 200:
        print(f"  Learn trigger failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    # 3. Poll status until complete
    status_url = f"{api_url}/api/templates/status/{job_id}"
    status: dict = {}
    for _ in range(30):
        time.sleep(1)
        status = requests.get(status_url).json()
        progress = status.get("progress", 0)
        print(f"\r  Learning ... {progress}%", end="", flush=True)
        if progress >= 100:
            break
    print()

    if status.get("error"):
        print(f"  Server error: {status['error']}", file=sys.stderr)
        sys.exit(1)

    return status


def _publish_via_api(template_id: str, user_id: str, api_url: str) -> None:
    """Publish a saved template to the global library."""
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        print("  ERROR: 'requests' package required for --publish.", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        f"{api_url}/api/templates/publish/{template_id}",
        params={"user_id": user_id},
    )
    if resp.status_code != 200:
        print(f"  Publish failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    print("  Published to global library.")


# ── CLI entry point ───────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser (exposed for testing)."""
    parser = argparse.ArgumentParser(
        prog="template_learner",
        description="Learn an audit PDF format from a reference document.",
    )
    parser.add_argument("--pdf", required=True, help="Path to the reference audit PDF")
    parser.add_argument("--name", required=True, help="Human-readable template name")
    parser.add_argument("--user-id", default="cli_user", help="Owner user ID (default: cli_user)")
    parser.add_argument("--save", action="store_true", help="Save template via REST API")
    parser.add_argument("--publish", action="store_true", help="Publish to global library (implies --save)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--skip-verify", action="store_true", help="Skip verification step")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    return parser


def main(argv: list | None = None) -> None:
    """Run the template learning CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # --publish implies --save
    if args.publish:
        args.save = True

    # Step 1 - Extract
    if not args.json_output:
        _print_header("Step 1: Extracting template from PDF")

    analyzer = TemplateAnalyzer()
    config = analyzer.analyze(str(pdf_path))

    if config.get("error"):
        print(f"  Warning: {config['error']}", file=sys.stderr)

    if not args.json_output:
        _print_config(config)

    # Step 2 - Verify
    report = None
    if not args.skip_verify:
        if not args.json_output:
            _print_header("Step 2: Verification report")

        verifier = TemplateVerifier()
        report = verifier.generate_report(config)

        if not args.json_output:
            _print_report(report)
    else:
        if not args.json_output:
            print("\n  (verification skipped)")

    # Step 3 - Save via API
    status = None
    if args.save:
        if not args.json_output:
            _print_header("Step 3: Saving to server")
        status = _save_via_api(str(pdf_path), args.name, args.user_id, args.api_url)
        if not args.json_output:
            print(f"  Template ID: {status.get('template_id', 'n/a')}")
            print(f"  Status:      {status.get('status', 'n/a')}")

    # Step 4 - Publish
    if args.publish and status and status.get("template_id"):
        if not args.json_output:
            _print_header("Step 4: Publishing to global library")
        _publish_via_api(status["template_id"], args.user_id, args.api_url)

    # JSON output
    if args.json_output:
        output = {
            "config": config,
            "report": report,
            "saved": status,
        }
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
