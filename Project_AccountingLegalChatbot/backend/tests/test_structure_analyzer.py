"""Tests for template structure analyzer."""
import pytest
from core.templates.structure_analyzer import analyze_structure


def test_detect_headings():
    body = "# Title\nSome text\n## Section A\nMore text\n### Sub-section"
    result = analyze_structure(body)
    assert len(result.sections) == 3
    assert result.sections[0].title == "Title"
    assert result.sections[0].level == 1
    assert result.sections[1].title == "Section A"
    assert result.sections[1].level == 2


def test_detect_variables():
    body = "Company: ${company_name}\nTRN: ${company_trn}\nPeriod: $period"
    result = analyze_structure(body)
    names = [v.name for v in result.variables]
    assert "company_name" in names
    assert "company_trn" in names
    assert "period" in names


def test_detect_tables():
    body = "| Account | Debit | Credit |\n| --- | --- | --- |\n| Cash | 100 | 0 |"
    result = analyze_structure(body)
    assert len(result.tables) == 1
    assert result.tables[0].columns == ["Account", "Debit", "Credit"]


def test_line_and_word_count():
    body = "Line one\nLine two\nLine three"
    result = analyze_structure(body)
    assert result.line_count == 3
    assert result.word_count == 6


def test_no_duplicate_variables():
    body = "${name} and ${name} again ${name}"
    result = analyze_structure(body)
    assert len(result.variables) == 1
