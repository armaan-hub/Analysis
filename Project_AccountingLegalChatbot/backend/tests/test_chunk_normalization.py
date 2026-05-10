"""Tests for _normalize_chunk() — standardizes raw RAG search output metadata."""
import pytest
from core.rag_engine import _normalize_chunk


class TestNormalizeChunk:
    """Verify _normalize_chunk maps raw RAGEngine.search() output to standard schema."""

    def _raw(self, **overrides):
        """Build a typical raw search result dict."""
        base = {
            "id": "chunk_abc123",
            "text": "The VAT rate applicable to ...",
            "metadata": {
                "original_name": "vat_guide_2024.pdf",
                "page_number": 7,
                "doc_id": "doc-uuid-001",
                "section": "Section 3.2",
            },
            "score": 0.87,
            "source": "vat_guide_2024.pdf",
        }
        base.update(overrides)
        return base

    def test_basic_mapping(self):
        raw = self._raw()
        result = _normalize_chunk(raw)
        assert result["chunk_id"] == "chunk_abc123"
        assert result["text"] == "The VAT rate applicable to ..."
        assert result["source_file"] == "vat_guide_2024.pdf"
        assert result["page"] == 7
        assert result["score"] == 0.87
        assert result["document_id"] == "doc-uuid-001"
        assert result["section"] == "Section 3.2"

    def test_output_has_exactly_seven_keys(self):
        result = _normalize_chunk(self._raw())
        assert set(result.keys()) == {
            "chunk_id", "text", "source_file", "page",
            "score", "document_id", "section"
        }

    def test_page_fallback_to_page_key(self):
        """Falls back to metadata['page'] if page_number absent."""
        raw = self._raw()
        del raw["metadata"]["page_number"]
        raw["metadata"]["page"] = 3
        result = _normalize_chunk(raw)
        assert result["page"] == 3

    def test_page_none_when_both_missing(self):
        """Returns None for page when neither page_number nor page present."""
        raw = self._raw()
        del raw["metadata"]["page_number"]
        result = _normalize_chunk(raw)
        assert result["page"] is None

    def test_source_file_from_metadata_original_name(self):
        """source_file comes from metadata.original_name."""
        raw = self._raw()
        raw["metadata"]["original_name"] = "labour_act_2023.pdf"
        raw["source"] = "something_else"
        result = _normalize_chunk(raw)
        assert result["source_file"] == "labour_act_2023.pdf"

    def test_source_file_fallback_to_source_key(self):
        """Falls back to top-level source field if original_name absent."""
        raw = self._raw()
        del raw["metadata"]["original_name"]
        raw["source"] = "fallback_source.pdf"
        result = _normalize_chunk(raw)
        assert result["source_file"] == "fallback_source.pdf"

    def test_document_id_from_metadata_doc_id(self):
        raw = self._raw()
        raw["metadata"]["doc_id"] = "specific-doc-id"
        result = _normalize_chunk(raw)
        assert result["document_id"] == "specific-doc-id"

    def test_section_none_when_absent(self):
        raw = self._raw()
        del raw["metadata"]["section"]
        result = _normalize_chunk(raw)
        assert result["section"] is None

    def test_empty_metadata(self):
        """Handles chunk with empty metadata dict gracefully."""
        raw = {
            "id": "bare-chunk",
            "text": "bare text",
            "metadata": {},
            "score": 0.5,
            "source": "bare.pdf",
        }
        result = _normalize_chunk(raw)
        assert result["chunk_id"] == "bare-chunk"
        assert result["source_file"] == "bare.pdf"
        assert result["page"] is None
        assert result["document_id"] is None
        assert result["section"] is None

    def test_returns_new_dict_not_mutation(self):
        """Result must be a new dict, not mutation of input."""
        raw = self._raw()
        original_meta = dict(raw["metadata"])
        result = _normalize_chunk(raw)
        assert raw["metadata"] == original_meta  # raw unchanged
        assert result is not raw
