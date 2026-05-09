"""Integration tests for the full source-file ingest pipeline."""
import pytest
import fitz
from pathlib import Path
from unittest.mock import AsyncMock, patch


@pytest.fixture
def sample_law_pdf(tmp_path) -> str:
    """Build a real (small) PDF with English legal text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), (
        "Federal Decree Law No. 50 of 2022 on the Regulation of Bounced Cheques. "
        "Article 1: This law governs the penalties for dishonoured cheques in the UAE. "
        "Article 15: Any person who issues a cheque that is returned due to insufficient funds "
        "shall be subject to a fine not exceeding AED 10,000."
    ))
    path = str(tmp_path / "DecreeLaw50_2022.pdf")
    doc.save(path)
    doc.close()
    return path


@pytest.mark.asyncio
async def test_ingest_source_file_creates_document_record(sample_law_pdf, db_session):
    """ingest_source_file() must create a Document row with new pipeline fields populated."""
    from core.llm_manager import MetadataResult
    mock_metadata = MetadataResult(
        domain="banking_compliance",
        jurisdiction="uae_federal",
        law_number="Decree Law 50 of 2022",
        subjects=["cheque bouncing", "penalties"],
        effective_date="2022-09-01",
        summary="Law on bounced cheques.",
    )

    with patch("core.document_processor.llm_manager") as mock_llm:
        mock_llm.extract_metadata = AsyncMock(return_value=mock_metadata)
        mock_llm.translate = AsyncMock(return_value="translated text")
        mock_llm._provider = AsyncMock()
        mock_llm._provider.chat = AsyncMock(return_value=type("R", (), {"content": '{"entities":[],"relationships":[]}'})())

        from core.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        doc = await processor.ingest_source_file(
            path=sample_law_pdf,
            source_dir="law",
            db=db_session,
        )

    assert doc is not None
    assert doc.source_dir == "law"
    assert doc.domain == "banking_compliance"
    assert doc.jurisdiction == "uae_federal"
    assert doc.status == "indexed"
    assert doc.is_arabic is False
    assert doc.indexed_at is not None


@pytest.mark.asyncio
async def test_ingest_source_file_skips_encrypted_pdf(tmp_path, db_session):
    """ingest_source_file() must set status='skipped' for encrypted PDFs."""
    import fitz
    # Create an encrypted PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Secret document")
    enc_path = str(tmp_path / "encrypted.pdf")
    doc.save(enc_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    doc.close()

    with patch("core.document_processor.llm_manager"):
        from core.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        result = await processor.ingest_source_file(
            path=enc_path,
            source_dir="law",
            db=db_session,
        )

    assert result.status == "skipped"


def test_smart_chunk_respects_size():
    """_smart_chunk must produce chunks <= 1.5 * chunk_size chars."""
    from core.document_processor import DocumentProcessor
    processor = DocumentProcessor()
    text = "Hello world. " * 500  # ~6500 chars
    chunks = processor._smart_chunk(text, chunk_size=800, overlap=150)
    assert len(chunks) >= 2
    max_allowed = int(800 * 1.5)
    for chunk in chunks:
        assert len(chunk) <= max_allowed, f"Chunk too large: {len(chunk)} > {max_allowed}"


def test_smart_chunk_short_text_returns_single_chunk():
    """_smart_chunk must return a single chunk for text shorter than chunk_size."""
    from core.document_processor import DocumentProcessor
    processor = DocumentProcessor()
    text = "Short legal text."
    chunks = processor._smart_chunk(text, chunk_size=800, overlap=150)
    assert len(chunks) == 1
    assert chunks[0] == text
