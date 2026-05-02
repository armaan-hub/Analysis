"""Tests for the learn-audit-format CLI (cli.template_learner)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cli.template_learner import build_parser, main


# ── Fixtures ──────────────────────────────────────────────────────

FAKE_CONFIG = {
    "page": {"width": 612, "height": 792, "unit": "points"},
    "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
    "fonts": {
        "heading": {"family": "Helvetica-Bold", "size": 14},
        "body": {"family": "Helvetica", "size": 10},
        "footer": {"family": "Helvetica", "size": 8},
    },
    "tables": [],
    "sections": [{"name": "cover", "page": 1, "layout": "static"}],
    "confidence": 0.7,
    "source": "test.pdf",
    "page_count": 5,
}

FAKE_REPORT = {
    "overall_passed": True,
    "confidence": 0.95,
    "checks": [
        {"check": "page_dimensions", "passed": True, "confidence": 1.0, "message": "OK"},
        {"check": "margins", "passed": True, "confidence": 1.0, "message": "OK"},
        {"check": "fonts", "passed": True, "confidence": 1.0, "message": "OK"},
        {"check": "sections", "passed": True, "confidence": 1.0, "message": "1 section(s) detected"},
    ],
    "summary": "4/4 checks passed",
}


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """Create a tiny dummy file to satisfy the 'file exists' check."""
    p = tmp_path / "test.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


# ── Argument parsing ─────────────────────────────────────────────


class TestArgumentParsing:
    def test_required_args(self):
        parser = build_parser()
        args = parser.parse_args(["--pdf", "a.pdf", "--name", "demo"])
        assert args.pdf == "a.pdf"
        assert args.name == "demo"

    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["--pdf", "a.pdf", "--name", "demo"])
        assert args.user_id == "cli_user"
        assert args.save is False
        assert args.publish is False
        assert args.api_url == "http://localhost:8000"
        assert args.skip_verify is False
        assert args.json_output is False

    def test_all_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "--pdf", "a.pdf",
            "--name", "demo",
            "--user-id", "u1",
            "--save",
            "--publish",
            "--api-url", "http://example.com",
            "--skip-verify",
            "--json",
        ])
        assert args.user_id == "u1"
        assert args.save is True
        assert args.publish is True
        assert args.api_url == "http://example.com"
        assert args.skip_verify is True
        assert args.json_output is True

    def test_missing_required_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ── Core workflow (analyze + verify, no server) ───────────────────


class TestCoreWorkflow:
    @patch("cli.template_learner.TemplateVerifier")
    @patch("cli.template_learner.TemplateAnalyzer")
    def test_extract_and_verify(self, MockAnalyzer, MockVerifier, fake_pdf, capsys):
        MockAnalyzer.return_value.analyze.return_value = FAKE_CONFIG
        MockVerifier.return_value.generate_report.return_value = FAKE_REPORT

        main(["--pdf", str(fake_pdf), "--name", "demo"])

        MockAnalyzer.return_value.analyze.assert_called_once_with(str(fake_pdf))
        MockVerifier.return_value.generate_report.assert_called_once_with(FAKE_CONFIG)

        out = capsys.readouterr().out
        assert "Extracting" in out
        assert "Verification" in out

    @patch("cli.template_learner.TemplateVerifier")
    @patch("cli.template_learner.TemplateAnalyzer")
    def test_skip_verify(self, MockAnalyzer, MockVerifier, fake_pdf, capsys):
        MockAnalyzer.return_value.analyze.return_value = FAKE_CONFIG

        main(["--pdf", str(fake_pdf), "--name", "demo", "--skip-verify"])

        MockVerifier.return_value.generate_report.assert_not_called()
        out = capsys.readouterr().out
        assert "skipped" in out

    @patch("cli.template_learner.TemplateVerifier")
    @patch("cli.template_learner.TemplateAnalyzer")
    def test_json_output(self, MockAnalyzer, MockVerifier, fake_pdf, capsys):
        MockAnalyzer.return_value.analyze.return_value = FAKE_CONFIG
        MockVerifier.return_value.generate_report.return_value = FAKE_REPORT

        main(["--pdf", str(fake_pdf), "--name", "demo", "--json"])

        raw = capsys.readouterr().out
        data = json.loads(raw)
        assert data["config"] == FAKE_CONFIG
        assert data["report"] == FAKE_REPORT
        assert data["saved"] is None


# ── Error handling ────────────────────────────────────────────────


class TestErrors:
    def test_missing_pdf_exits(self):
        with pytest.raises(SystemExit):
            main(["--pdf", "no_such_file.pdf", "--name", "x"])

    @patch("cli.template_learner.TemplateAnalyzer")
    def test_analyzer_error_shown(self, MockAnalyzer, fake_pdf, capsys):
        cfg = {**FAKE_CONFIG, "error": "PyMuPDF not installed"}
        MockAnalyzer.return_value.analyze.return_value = cfg

        main(["--pdf", str(fake_pdf), "--name", "demo", "--skip-verify"])

        err = capsys.readouterr().err
        assert "PyMuPDF not installed" in err


# ── --publish implies --save ──────────────────────────────────────


class TestPublishImpliesSave:
    @patch("cli.template_learner._publish_via_api")
    @patch("cli.template_learner._save_via_api")
    @patch("cli.template_learner.TemplateVerifier")
    @patch("cli.template_learner.TemplateAnalyzer")
    def test_publish_triggers_save(
        self, MockAnalyzer, MockVerifier, mock_save, mock_publish, fake_pdf
    ):
        MockAnalyzer.return_value.analyze.return_value = FAKE_CONFIG
        MockVerifier.return_value.generate_report.return_value = FAKE_REPORT
        mock_save.return_value = {"template_id": "t-123", "status": "verified"}

        main(["--pdf", str(fake_pdf), "--name", "demo", "--publish"])

        mock_save.assert_called_once()
        mock_publish.assert_called_once_with("t-123", "cli_user", "http://localhost:8000")
