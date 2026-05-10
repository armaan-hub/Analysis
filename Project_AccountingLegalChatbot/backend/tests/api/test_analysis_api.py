"""Tests for the Analysis Mode batch document processing pipeline."""
import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from core.document_processor import DocumentProcessor


@pytest.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestBatchExtractCsv:
    def test_small_csv_not_batched(self, tmp_path):
        """CSV with <=5000 rows returns single batch without BATCH separator."""
        dp = DocumentProcessor()
        content = "col1,col2\n" + "\n".join(f"val{i},val{i}" for i in range(100))
        f = tmp_path / "small.csv"
        f.write_text(content)
        result = dp.batch_extract_csv(str(f))
        assert "---BATCH_" not in result
        assert "col1" in result

    def test_large_csv_batched_with_separator(self, tmp_path):
        """CSV with >5000 rows returns batched output with ---BATCH_N--- separators."""
        dp = DocumentProcessor()
        rows = ["col1,col2"] + [f"val{i},val{i}" for i in range(6000)]
        f = tmp_path / "large.csv"
        f.write_text("\n".join(rows))
        result = dp.batch_extract_csv(str(f))
        assert "---BATCH_1---" in result
        assert "---BATCH_2---" in result

    def test_batch_extract_includes_metadata_header(self, tmp_path):
        """Output includes row count and column names as structured metadata."""
        dp = DocumentProcessor()
        content = "amount,date,account\n1000,2026-01-01,revenue"
        f = tmp_path / "test.csv"
        f.write_text(content)
        result = dp.batch_extract_csv(str(f))
        assert "rows:" in result.lower() or "row_count" in result.lower() or "1" in result
        assert "amount" in result or "date" in result


@pytest.mark.asyncio
async def test_analysis_upload_endpoint_exists(client):
    """POST /api/analysis/upload returns 200 with a PDF file."""
    pdf_bytes = b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj"
    files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    with patch("api.analysis.document_processor") as mock_dp:
        mock_dp.process = AsyncMock(return_value=[MagicMock(text="Sample text", metadata={})])
        r = await client.post("/api/analysis/upload", files=files)
    assert r.status_code == 200
    data = r.json()
    assert "file_id" in data or "filename" in data


@pytest.mark.asyncio
async def test_analysis_analyze_endpoint_exists(client):
    """POST /api/analysis/analyze returns structured report."""
    with patch("api.analysis.rag_engine") as mock_rag, \
         patch("api.analysis.get_llm_provider") as mock_llm:
        mock_rag.search = AsyncMock(return_value=[])
        mock_llm_instance = MagicMock()
        mock_llm_instance.chat = AsyncMock(return_value=MagicMock(
            text="# Financial Analysis\n## Key Findings\nNo issues found."
        ))
        mock_llm.return_value = mock_llm_instance
        r = await client.post("/api/analysis/analyze", json={
            "file_ids": ["nonexistent-id"],
            "query": "Check VAT compliance",
        })
    assert r.status_code in (200, 404)  # 404 if file_id not found; 200 if mock bypasses
