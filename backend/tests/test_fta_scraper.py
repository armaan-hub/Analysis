"""Tests for core.pipeline.fta_scraper — no real network calls."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _pdf_bytes() -> bytes:
    return b"%PDF-1.4 fake pdf content for unit testing"


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _make_async_client_mock(side_effects: list) -> MagicMock:
    """Build an async-context-manager mock for httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=side_effects)
    return mock_client


def _ok_response(text: str = "", content: bytes = b"") -> MagicMock:
    r = MagicMock()
    r.text = text
    r.content = content
    r.raise_for_status = MagicMock()
    return r


def _error_response() -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock(side_effect=Exception("HTTP 404"))
    return r


# ── 1. _md5_of returns a 32-char hex string ───────────────────────────────────

def test_md5_of_returns_hex_string():
    from core.pipeline.fta_scraper import _md5_of

    result = _md5_of(b"data")
    assert isinstance(result, str)
    assert len(result) == 32
    assert all(c in "0123456789abcdef" for c in result)


# ── 2. _safe_filename sanitises special chars, always ends in .pdf ────────────

def test_safe_filename_sanitizes_url():
    from core.pipeline.fta_scraper import _safe_filename

    result = _safe_filename("https://tax.gov.ae/en/law files/vat guide (2024).pdf")
    assert result.endswith(".pdf")
    assert " " not in result
    assert "(" not in result
    assert ")" not in result


def test_safe_filename_adds_pdf_extension_when_missing():
    from core.pipeline.fta_scraper import _safe_filename

    result = _safe_filename("https://tax.gov.ae/docs/vatlaw")
    assert result.endswith(".pdf")


# ── 3. Already-seen MD5 is skipped — count stays 0 ───────────────────────────

async def test_md5_dedup_skips_seen_file(tmp_path):
    from core.pipeline import fta_scraper

    pdf = _pdf_bytes()
    known_md5 = _md5(pdf)
    hash_file = tmp_path / "scraped_hashes.txt"
    hash_file.write_text(known_md5 + "\n", encoding="utf-8")
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    # Portal returns a page with one PDF link; the PDF bytes have the known hash
    page_resp = _ok_response(text='<a href="/doc.pdf">PDF</a>')
    pdf_resp = _ok_response(content=pdf)
    mock_client = _make_async_client_mock([page_resp, pdf_resp])

    with (
        patch.object(fta_scraper, "_HASH_FILE", hash_file),
        patch.object(fta_scraper, "_DOWNLOAD_DIR", download_dir),
        patch.object(fta_scraper, "_SCRAPE_URLS", ["https://tax.gov.ae/en/laws.aspx"]),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        count = await fta_scraper.scrape_and_ingest()

    assert count == 0
    assert list(download_dir.iterdir()) == []


# ── 4. New PDF is downloaded, saved to disk, and hash persisted ───────────────

async def test_new_pdf_is_downloaded_and_saved(tmp_path):
    from core.pipeline import fta_scraper

    pdf = _pdf_bytes()
    hash_file = tmp_path / "scraped_hashes.txt"
    hash_file.write_text("", encoding="utf-8")
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    page_resp = _ok_response(text='<a href="/vat_guide.pdf">VAT Guide</a>')
    pdf_resp = _ok_response(content=pdf)
    mock_client = _make_async_client_mock([page_resp, pdf_resp])

    with (
        patch.object(fta_scraper, "_HASH_FILE", hash_file),
        patch.object(fta_scraper, "_DOWNLOAD_DIR", download_dir),
        patch.object(fta_scraper, "_SCRAPE_URLS", ["https://tax.gov.ae/en/laws.aspx"]),
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("core.document_processor.ingest_text", new=AsyncMock()),
        patch.object(fta_scraper, "_extract_text_from_bytes", return_value="sample law text"),
    ):
        count = await fta_scraper.scrape_and_ingest()

    assert count == 1
    saved = list(download_dir.iterdir())
    assert len(saved) == 1
    assert saved[0].suffix == ".pdf"
    persisted = hash_file.read_text(encoding="utf-8").strip().splitlines()
    assert _md5(pdf) in persisted


# ── 5. Failed portal fetch is logged and scraper continues to next portal ─────

async def test_failed_portal_fetch_continues(tmp_path):
    from core.pipeline import fta_scraper

    pdf = _pdf_bytes()
    hash_file = tmp_path / "scraped_hashes.txt"
    hash_file.write_text("", encoding="utf-8")
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    # First portal → HTTP error; second portal → success
    fail_resp = _error_response()
    page_resp = _ok_response(text='<a href="/law.pdf">Law</a>')
    pdf_resp = _ok_response(content=pdf)
    mock_client = _make_async_client_mock([fail_resp, page_resp, pdf_resp])

    with (
        patch.object(fta_scraper, "_HASH_FILE", hash_file),
        patch.object(fta_scraper, "_DOWNLOAD_DIR", download_dir),
        patch.object(fta_scraper, "_SCRAPE_URLS", [
            "https://tax.gov.ae/en/laws.aspx",
            "https://www.moec.gov.ae/en/laws-and-legislations",
        ]),
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("core.document_processor.ingest_text", new=AsyncMock()),
        patch.object(fta_scraper, "_extract_text_from_bytes", return_value="text"),
    ):
        count = await fta_scraper.scrape_and_ingest()

    # Second portal still scraped one file despite first portal failing
    assert count == 1
