"""Tests for section heading extraction and enriched chunk metadata."""
import pytest
from core.document_processor import DocumentProcessor, DocumentChunk


@pytest.fixture
def proc():
    return DocumentProcessor(chunk_size=200, chunk_overlap=20)


def test_section_extracted_from_heading_line(proc):
    """A line starting with uppercase words followed by content is detected as a section."""
    pages = [{"text": "WILLS AND INHERITANCE\nThis section covers how wills are made.", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    assert len(chunks) >= 1
    sections = [c.metadata.get("section", "") for c in chunks]
    assert any("WILLS" in s.upper() for s in sections), f"sections={sections}"


def test_section_defaults_to_empty_string(proc):
    """Chunks with no detectable heading get section='' not None."""
    pages = [{"text": "some lowercase plain text without any heading here", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    for c in chunks:
        assert "section" in c.metadata
        assert c.metadata["section"] == ""


def test_chunk_metadata_has_word_count(proc):
    """Every chunk must have a word_count int field > 0."""
    pages = [{"text": "The quick brown fox jumps over the lazy dog.", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    for c in chunks:
        assert "word_count" in c.metadata
        assert isinstance(c.metadata["word_count"], int)
        assert c.metadata["word_count"] > 0


def test_chunk_metadata_has_total_chunks(proc):
    """Every chunk in a doc must carry the same total_chunks count."""
    # 500-char text with chunk_size=200 → at least 3 chunks
    text = "word " * 100
    pages = [{"text": text, "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    assert len(chunks) >= 2
    totals = {c.metadata["total_chunks"] for c in chunks}
    assert totals == {len(chunks)}, f"expected single total={len(chunks)}, got {totals}"


def test_chunk_index_sequential(proc):
    """chunk_index should be 0, 1, 2, ... across the whole document."""
    text = "word " * 100
    pages = [{"text": text, "page": 1}, {"text": text, "page": 2}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    indices = [c.metadata["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))


def test_section_propagates_across_page_boundary(proc):
    """Section detected on page 1 should carry over to page 2 chunks with no heading."""
    pages = [
        {"text": "WILLS AND INHERITANCE\nSome content about wills on page one.", "page": 1},
        {"text": "More content continuing the same topic without a new heading.", "page": 2},
    ]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    # All chunks on page 2 should inherit the heading from page 1
    page2_chunks = [c for c in chunks if c.metadata["page"] == "2"]
    assert page2_chunks, "expected at least one chunk on page 2"
    for c in page2_chunks:
        assert c.metadata["section"] == "WILLS AND INHERITANCE", (
            f"expected section carried from page 1, got {c.metadata['section']!r}"
        )


@pytest.mark.parametrize("line,expected_nonempty", [
    ("Article 4 – Distribution of Estate", True),
    ("OVERVIEW OF UAE TAX LAW", True),
    ("This is a sentence.", False),
    ("2024", False),
])
def test_extract_heading_from_text_direct(line, expected_nonempty):
    """_extract_heading_from_text returns a non-empty string for headings, '' otherwise."""
    result = DocumentProcessor._extract_heading_from_text(line)
    if expected_nonempty:
        assert result != "", f"expected heading detected for {line!r}, got empty string"
    else:
        assert result == "", f"expected no heading for {line!r}, got {result!r}"

