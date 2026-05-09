"""Tests for config source-dir settings and SourceScanner."""
import os
import hashlib
import pytest
from pathlib import Path


# ── Config tests ──────────────────────────────────────────────────────────────

def test_config_has_source_dir_settings():
    """Config must expose source_law_dir, source_finance_dir, entity_graph_db."""
    from config import Settings
    s = Settings()
    assert hasattr(s, "source_law_dir")
    assert hasattr(s, "source_finance_dir")
    assert hasattr(s, "entity_graph_db")


def test_source_dirs_default_to_backend_relative():
    """Default paths must resolve to absolute paths."""
    from config import Settings
    s = Settings()
    assert os.path.isabs(s.source_law_dir),     "source_law_dir must be absolute"
    assert os.path.isabs(s.source_finance_dir), "source_finance_dir must be absolute"
    assert os.path.isabs(s.entity_graph_db),    "entity_graph_db must be absolute"


# ── SourceScanner tests (added in Task 6) ─────────────────────────────────────
pytest.importorskip("core.pipeline.source_scanner", reason="Task 6 (source_scanner) not yet implemented")

def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_scanner_detects_new_files(tmp_path):
    """SourceScanner must queue files not in the registry."""
    from core.pipeline.source_scanner import SourceScanner

    f1 = tmp_path / "law1.pdf"
    f2 = tmp_path / "law2.pdf"
    f1.write_bytes(b"%PDF fake law 1")
    f2.write_bytes(b"%PDF fake law 2")

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={},
    )
    pending = scanner.scan()
    paths = [p.path for p in pending]
    assert str(f1) in paths
    assert str(f2) in paths


@pytest.mark.asyncio
async def test_scanner_skips_unchanged_files(tmp_path):
    """SourceScanner must skip files whose hash matches the registry."""
    from core.pipeline.source_scanner import SourceScanner

    f1 = tmp_path / "law1.pdf"
    f1.write_bytes(b"%PDF unchanged content")
    h = _sha256(str(f1))

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={str(f1): h},
    )
    pending = scanner.scan()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_scanner_queues_changed_files(tmp_path):
    """SourceScanner must re-queue files whose hash changed."""
    from core.pipeline.source_scanner import SourceScanner

    f1 = tmp_path / "law1.pdf"
    f1.write_bytes(b"%PDF new content v2")
    old_hash = "aaaaaa"

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={str(f1): old_hash},
    )
    pending = scanner.scan()
    assert len(pending) == 1
    assert pending[0].path == str(f1)


def test_pending_file_has_correct_source_dir(tmp_path):
    """PendingFile.source_dir must be 'law' or 'finance' based on watch dir."""
    from core.pipeline.source_scanner import SourceScanner

    law_dir = tmp_path / "law"
    fin_dir = tmp_path / "finance"
    law_dir.mkdir()
    fin_dir.mkdir()
    (law_dir / "law1.pdf").write_bytes(b"%PDF")
    (fin_dir / "fin1.pdf").write_bytes(b"%PDF")

    scanner = SourceScanner(
        source_law_dir=str(law_dir),
        source_finance_dir=str(fin_dir),
        registry={},
    )
    pending = scanner.scan()
    by_cat = {p.path: p.source_dir for p in pending}
    assert by_cat[str(law_dir / "law1.pdf")] == "law"
    assert by_cat[str(fin_dir / "fin1.pdf")] == "finance"
