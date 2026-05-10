"""Tests for citation injection in chat.py — CITATION_INSTRUCTION and _inject_citation_fallback."""
import pytest
from api.chat import CITATION_INSTRUCTION, _inject_citation_fallback
from core.rag_engine import _normalize_chunk


class TestCitationInstruction:
    """Verify CITATION_INSTRUCTION constant is well-formed."""

    def test_instruction_is_non_empty_string(self):
        assert isinstance(CITATION_INSTRUCTION, str)
        assert len(CITATION_INSTRUCTION) > 50

    def test_instruction_mentions_citations(self):
        lower = CITATION_INSTRUCTION.lower()
        assert "cit" in lower or "source" in lower or "reference" in lower


class TestInjectCitationFallback:
    """Verify _inject_citation_fallback appends sources when LLM skips citations."""

    def _chunk(self, source_file, page=None, score=0.8):
        return {
            "chunk_id": "c1",
            "text": "...",
            "source_file": source_file,
            "page": page,
            "score": score,
            "document_id": "doc-1",
            "section": None,
        }

    def test_no_change_when_citation_present(self):
        """If response already has citation markers, do not append anything."""
        chunks = [self._chunk("vat_guide.pdf", page=3)]
        response = "The VAT rate is 5% [Source: vat_guide.pdf, p.3]"
        result = _inject_citation_fallback(response, chunks)
        # Should not double-append
        assert result.count("vat_guide.pdf") == 1

    def test_appends_sources_when_no_citation(self):
        """If response has no citation markers, append source list."""
        chunks = [self._chunk("labour_act.pdf", page=7)]
        response = "The notice period is 30 days."
        result = _inject_citation_fallback(response, chunks)
        assert "labour_act.pdf" in result
        # Appended section must be separate from original response
        assert result.startswith("The notice period is 30 days.")

    def test_appends_page_number_when_present(self):
        chunks = [self._chunk("ifrs_guide.pdf", page=42)]
        result = _inject_citation_fallback("IFRS requires disclosure.", chunks)
        assert "42" in result

    def test_no_page_when_page_is_none(self):
        chunks = [self._chunk("corporate_tax.pdf", page=None)]
        result = _inject_citation_fallback("Tax rate is 9%.", chunks)
        assert "corporate_tax.pdf" in result
        # Should not show "None" or "p.None"
        assert "None" not in result

    def test_multiple_chunks_deduplicated(self):
        """Same source_file from multiple chunks should appear once."""
        chunks = [
            self._chunk("vat.pdf", page=1),
            self._chunk("vat.pdf", page=2),
            self._chunk("other.pdf", page=5),
        ]
        result = _inject_citation_fallback("Summary.", chunks)
        assert result.count("vat.pdf") == 1
        assert "other.pdf" in result

    def test_empty_chunks_returns_original(self):
        """With no chunks, return original response unchanged."""
        result = _inject_citation_fallback("Some answer.", [])
        assert result == "Some answer."

    def test_returns_string(self):
        chunks = [self._chunk("doc.pdf")]
        result = _inject_citation_fallback("answer", chunks)
        assert isinstance(result, str)

    def test_no_false_positive_on_city_word(self):
        """'city' must NOT be treated as citation marker."""
        chunks = [self._chunk("doc.pdf")]
        response = "The city of Dubai has regulations."
        result = _inject_citation_fallback(response, chunks)
        # Should have appended sources (not skipped due to "cit" substring)
        assert "doc.pdf" in result
