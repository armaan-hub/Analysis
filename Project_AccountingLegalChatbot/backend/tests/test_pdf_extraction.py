import pytest
from db.models import Document


def test_document_model_has_new_rag_fields():
    """Document model must carry pipeline fields before we can test anything else."""
    required = {
        "source_dir", "domain", "jurisdiction", "law_number",
        "subjects", "effective_date", "is_arabic", "was_translated", "indexed_at",
    }
    cols = {c.key for c in Document.__table__.columns}
    missing = required - cols
    assert not missing, f"Document model missing columns: {missing}"

from unittest.mock import patch, MagicMock

# ── Arabic detection ──────────────────────────────────────────────────────────

def test_is_arabic_detects_arabic_text():
    from core.pipeline.pdf_extractor import _is_arabic
    arabic = "هذا نص عربي طويل بما يكفي للكشف عنه كنص عربي"
    assert _is_arabic(arabic) is True

def test_is_arabic_rejects_english():
    from core.pipeline.pdf_extractor import _is_arabic
    english = "This is a long English sentence about UAE commercial law and contracts."
    assert _is_arabic(english) is False

def test_is_arabic_threshold_30_percent():
    from core.pipeline.pdf_extractor import _is_arabic
    mixed = "English words " * 6 + "عربي"
    assert _is_arabic(mixed) is False

# ── ExtractionResult dataclass ────────────────────────────────────────────────

def test_extraction_result_fields():
    from core.pipeline.pdf_extractor import ExtractionResult
    r = ExtractionResult(text="hello", page_count=2, is_arabic=False, skipped=False, skip_reason=None)
    assert r.text == "hello"
    assert r.page_count == 2
    assert r.is_arabic is False
    assert r.skipped is False

# ── extract_text mocked ───────────────────────────────────────────────────────

def test_extract_text_returns_result_for_valid_pdf(tmp_path):
    from core.pipeline.pdf_extractor import extract_text
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world, this is a test PDF for ingestion.")
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    result = extract_text(str(pdf_path))
    assert result.skipped is False
    assert "Hello world" in result.text
    assert result.page_count == 1
    assert result.is_arabic is False

def test_extract_text_detects_encrypted_pdf(tmp_path):
    from core.pipeline.pdf_extractor import extract_text
    import fitz
    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / "enc.pdf"
    doc.save(str(pdf_path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secret", user_pw="secret")
    doc.close()
    result = extract_text(str(pdf_path))
    assert result.skipped is True
    assert result.skip_reason is not None
    assert "encrypt" in result.skip_reason.lower() or "password" in result.skip_reason.lower()
