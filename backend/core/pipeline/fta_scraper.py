"""Auto-downloads new UAE tax/law PDFs from government portals.

Uses MD5 hash deduplication: already-seen files are skipped regardless of
filename changes. Hashes are persisted in data/scraped_hashes.txt.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# Government portals to scrape for PDF links
_SCRAPE_URLS: list[str] = [
    "https://tax.gov.ae/en/laws.aspx",
    "https://www.moec.gov.ae/en/laws-and-legislations",
    "https://www.mohre.gov.ae/en/laws",
]

_HASH_FILE = Path(__file__).parent.parent.parent / "data" / "scraped_hashes.txt"
_DOWNLOAD_DIR = Path(__file__).parent.parent.parent / "data_source_law"

_PDF_PATTERN = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.IGNORECASE)


def _load_seen_hashes() -> set[str]:
    """Load previously seen MD5 hashes from the hash file."""
    if not _HASH_FILE.exists():
        return set()
    return set(_HASH_FILE.read_text(encoding="utf-8").splitlines())


def _save_hash(md5: str) -> None:
    """Append a new MD5 hash to the hash file."""
    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _HASH_FILE.open("a", encoding="utf-8") as f:
        f.write(md5 + "\n")


def _md5_of(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _safe_filename(url: str) -> str:
    """Derive a safe local filename from a PDF URL."""
    name = Path(urlparse(url).path).name
    name = re.sub(r'[^\w\-.]', '_', name)
    return name if name.endswith('.pdf') else name + '.pdf'


def _extract_text_from_bytes(pdf_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF bytes using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            return "\n".join(page.get_text("text") or "" for page in doc)
        finally:
            doc.close()
    except Exception as exc:
        logger.warning("PDF text extraction failed for %s: %s", filename, exc)
        return ""


async def scrape_and_ingest() -> int:
    """Scrape all configured portals, download new PDFs, ingest them.

    Returns the number of new documents ingested.
    """
    seen_hashes = _load_seen_hashes()
    _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    new_count = 0

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for base_url in _SCRAPE_URLS:
            try:
                resp = await client.get(base_url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", base_url, exc)
                continue

            pdf_links = _PDF_PATTERN.findall(resp.text)
            for relative_link in pdf_links:
                pdf_url = urljoin(base_url, relative_link)
                try:
                    pdf_resp = await client.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
                    pdf_resp.raise_for_status()
                    pdf_bytes = pdf_resp.content
                except Exception as exc:
                    logger.warning("Failed to download %s: %s", pdf_url, exc)
                    continue

                md5 = _md5_of(pdf_bytes)
                if md5 in seen_hashes:
                    logger.debug("Skipping already-seen PDF: %s (%s)", pdf_url, md5)
                    continue

                filename = _safe_filename(pdf_url)
                dest = _DOWNLOAD_DIR / filename
                if dest.exists():
                    dest = _DOWNLOAD_DIR / f"{dest.stem}_{md5[:8]}.pdf"

                dest.write_bytes(pdf_bytes)
                logger.info("Downloaded new PDF: %s -> %s", pdf_url, dest.name)

                # Import here to avoid circular deps at module load
                try:
                    from core.document_processor import ingest_text
                    text = _extract_text_from_bytes(pdf_bytes, dest.name)
                    if text.strip():
                        await ingest_text(text, source=dest.name, category="law")
                        logger.info("Ingested: %s", dest.name)
                except Exception as exc:
                    logger.warning("Ingestion failed for %s: %s", dest.name, exc)

                _save_hash(md5)
                seen_hashes.add(md5)
                new_count += 1

    logger.info("FTA scraper complete: %d new documents ingested", new_count)
    return new_count
