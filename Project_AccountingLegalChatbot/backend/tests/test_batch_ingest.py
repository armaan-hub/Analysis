"""
Tests for backend/scripts/batch_ingest.py
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend/ is importable from tests/
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts.batch_ingest import (
    SUPPORTED_EXTENSIONS,
    collect_source_files,
    compute_sha256,
    is_already_indexed,
    save_progress_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(tmp_path: Path, name: str, content: bytes = b"hello") -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# collect_source_files
# ---------------------------------------------------------------------------

def test_collect_source_files_finds_supported_types(tmp_path):
    law_dir = tmp_path / "law"
    finance_dir = tmp_path / "finance"
    law_dir.mkdir()
    finance_dir.mkdir()

    # Supported files
    _make_file(law_dir, "regulation.pdf")
    _make_file(law_dir, "contract.docx")
    _make_file(finance_dir, "accounts.xlsx")
    # Unsupported – should be excluded
    _make_file(law_dir, "readme.txt")
    _make_file(finance_dir, "image.png")

    with (
        patch("scripts.batch_ingest.settings") as mock_settings,
    ):
        mock_settings.source_law_dir = str(law_dir)
        mock_settings.source_finance_dir = str(finance_dir)

        results = collect_source_files()

    paths = [p for p, _ in results]
    names = {p.name for p in paths}

    assert "regulation.pdf" in names
    assert "contract.docx" in names
    assert "accounts.xlsx" in names
    assert "readme.txt" not in names
    assert "image.png" not in names


def test_collect_source_files_labels(tmp_path):
    law_dir = tmp_path / "law"
    finance_dir = tmp_path / "finance"
    law_dir.mkdir()
    finance_dir.mkdir()

    _make_file(law_dir, "a.pdf")
    _make_file(finance_dir, "b.xlsx")

    with patch("scripts.batch_ingest.settings") as mock_settings:
        mock_settings.source_law_dir = str(law_dir)
        mock_settings.source_finance_dir = str(finance_dir)

        results = collect_source_files()

    label_map = {p.name: label for p, label in results}
    assert label_map["a.pdf"] == "law"
    assert label_map["b.xlsx"] == "finance"


def test_collect_source_files_missing_dir(tmp_path, capsys):
    """Missing directories should produce a warning and return empty list."""
    with patch("scripts.batch_ingest.settings") as mock_settings:
        mock_settings.source_law_dir = str(tmp_path / "nonexistent_law")
        mock_settings.source_finance_dir = str(tmp_path / "nonexistent_finance")

        results = collect_source_files()

    assert results == []
    captured = capsys.readouterr()
    assert "[WARN]" in captured.out


# ---------------------------------------------------------------------------
# is_already_indexed
# ---------------------------------------------------------------------------

async def test_is_already_indexed_returns_true_when_hash_matches(tmp_path):
    """If DB has a document with matching hash and indexed_at set, return True."""
    content = b"test document content"
    test_file = _make_file(tmp_path, "doc.pdf", content)
    expected_hash = hashlib.sha256(content).hexdigest()

    mock_doc = MagicMock()
    mock_doc.content_hash = expected_hash
    mock_doc.indexed_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_already_indexed(test_file, mock_db)
    assert result is True


async def test_is_already_indexed_returns_false_when_no_match(tmp_path):
    """Return False when no matching document in DB."""
    test_file = _make_file(tmp_path, "doc.pdf", b"content")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await is_already_indexed(test_file, mock_db)
    assert result is False


# ---------------------------------------------------------------------------
# save_progress_log
# ---------------------------------------------------------------------------

def test_save_progress_log_writes_valid_json(tmp_path):
    log_path = tmp_path / "ingest_log.json"

    with patch("scripts.batch_ingest.LOG_PATH", log_path):
        save_progress_log(
            total=10,
            processed=8,
            skipped=1,
            errors=1,
            error_details=[{"file": "bad.pdf", "error": "parse failed"}],
        )

    assert log_path.exists()
    data = json.loads(log_path.read_text())

    assert data["total"] == 10
    assert data["processed"] == 8
    assert data["skipped"] == 1
    assert data["errors"] == 1
    assert len(data["error_details"]) == 1
    assert data["error_details"][0]["file"] == "bad.pdf"
    # Timestamp should be parseable ISO format
    datetime.fromisoformat(data["timestamp"])


# ---------------------------------------------------------------------------
# run_batch_ingest – skip/process logic
# ---------------------------------------------------------------------------

async def test_run_batch_ingest_skips_indexed_files(tmp_path, capsys):
    """Files already indexed should be skipped; ingest_source_file not called."""
    law_dir = tmp_path / "law"
    law_dir.mkdir()
    _make_file(law_dir, "indexed.pdf", b"already done")

    finance_dir = tmp_path / "finance"
    finance_dir.mkdir()

    mock_ingest = AsyncMock()
    mock_db_instance = AsyncMock()
    mock_db_instance.__aenter__ = AsyncMock(return_value=mock_db_instance)
    mock_db_instance.__aexit__ = AsyncMock(return_value=False)

    # Simulate: already indexed
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_db_instance.execute = AsyncMock(return_value=mock_result)

    with (
        patch("scripts.batch_ingest.settings") as mock_settings,
        patch("scripts.batch_ingest.AsyncSessionLocal", return_value=mock_db_instance),
        patch("scripts.batch_ingest.asyncio.sleep", new_callable=AsyncMock),
        patch("scripts.batch_ingest.LOG_PATH", tmp_path / "log.json"),
        patch("core.document_processor.DocumentProcessor") as MockDP,
    ):
        mock_settings.source_law_dir = str(law_dir)
        mock_settings.source_finance_dir = str(finance_dir)
        MockDP.return_value.ingest_source_file = mock_ingest

        from scripts.batch_ingest import run_batch_ingest
        await run_batch_ingest()

    mock_ingest.assert_not_called()
    captured = capsys.readouterr()
    assert "[SKIP]" in captured.out


async def test_run_batch_ingest_processes_pending_file(tmp_path, capsys):
    """Un-indexed files should be passed to ingest_source_file."""
    law_dir = tmp_path / "law"
    law_dir.mkdir()
    _make_file(law_dir, "pending.pdf", b"new content")

    finance_dir = tmp_path / "finance"
    finance_dir.mkdir()

    mock_ingest = AsyncMock(return_value=MagicMock())

    mock_db_instance = AsyncMock()
    mock_db_instance.__aenter__ = AsyncMock(return_value=mock_db_instance)
    mock_db_instance.__aexit__ = AsyncMock(return_value=False)

    # Simulate: not yet indexed
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_instance.execute = AsyncMock(return_value=mock_result)

    with (
        patch("scripts.batch_ingest.settings") as mock_settings,
        patch("scripts.batch_ingest.AsyncSessionLocal", return_value=mock_db_instance),
        patch("scripts.batch_ingest.asyncio.sleep", new_callable=AsyncMock),
        patch("scripts.batch_ingest.LOG_PATH", tmp_path / "log.json"),
        patch("core.document_processor.DocumentProcessor") as MockDP,
    ):
        mock_settings.source_law_dir = str(law_dir)
        mock_settings.source_finance_dir = str(finance_dir)
        MockDP.return_value.ingest_source_file = mock_ingest

        from scripts.batch_ingest import run_batch_ingest
        await run_batch_ingest()

    mock_ingest.assert_called_once()
    captured = capsys.readouterr()
    assert "[OK]" in captured.out


async def test_run_batch_ingest_continues_after_error(tmp_path, capsys):
    """A per-file error must not abort the run; [ERROR] is printed and logged."""
    law_dir = tmp_path / "law"
    law_dir.mkdir()
    _make_file(law_dir, "bad.pdf", b"corrupt")
    _make_file(law_dir, "good.pdf", b"valid")

    finance_dir = tmp_path / "finance"
    finance_dir.mkdir()

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("parse failure")
        return MagicMock()

    mock_db_instance = AsyncMock()
    mock_db_instance.__aenter__ = AsyncMock(return_value=mock_db_instance)
    mock_db_instance.__aexit__ = AsyncMock(return_value=False)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_instance.execute = AsyncMock(return_value=mock_result)

    with (
        patch("scripts.batch_ingest.settings") as mock_settings,
        patch("scripts.batch_ingest.AsyncSessionLocal", return_value=mock_db_instance),
        patch("scripts.batch_ingest.asyncio.sleep", new_callable=AsyncMock),
        patch("scripts.batch_ingest.LOG_PATH", tmp_path / "log.json"),
        patch("core.document_processor.DocumentProcessor") as MockDP,
    ):
        mock_settings.source_law_dir = str(law_dir)
        mock_settings.source_finance_dir = str(finance_dir)
        MockDP.return_value.ingest_source_file = side_effect

        from scripts.batch_ingest import run_batch_ingest
        await run_batch_ingest()

    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out
    assert "[OK]" in captured.out

    log_data = json.loads((tmp_path / "log.json").read_text())
    assert log_data["errors"] == 1
    assert log_data["processed"] == 1
