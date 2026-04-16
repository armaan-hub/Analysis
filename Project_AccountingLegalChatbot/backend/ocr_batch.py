"""
OCR batch processor for scanned Arabic PDFs that failed text extraction.

Usage (run from the backend/ directory, with venv activated):
    python ocr_batch.py

Requirements:
    pip install pdf2image pytesseract Pillow
    Tesseract OCR must be installed with the Arabic language pack:
      Windows: https://github.com/UB-Mannheim/tesseract/wiki
               During install, tick "Additional script data (Arabic)" under "Additional language data"
      Verify:  tesseract --list-langs  (should show 'ara')

What this script does:
    1. Reads each of the 8 known failing PDFs from the data source directories.
    2. Converts each page to an image using pdf2image (requires poppler on PATH).
    3. Runs pytesseract OCR with Arabic language support.
    4. Writes extracted text to a .txt file alongside the original PDF.
    5. Calls bulk_ingest to re-ingest all documents including the new .txt files.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── OCR dependency check ──────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image
except ImportError as e:
    logger.error(
        f"Missing dependency: {e}\n"
        "Install with: pip install pdf2image pytesseract Pillow\n"
        "Also install Tesseract OCR with Arabic language pack from:\n"
        "  https://github.com/UB-Mannheim/tesseract/wiki"
    )
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIRS = [
    PROJECT_DIR / "data_source_law",
    PROJECT_DIR / "data_source_finance",
]

# The 8 known-failing Arabic PDFs (scanned / image-only)
KNOWN_FAILING = [
    "المرسوم بقانون بشان تعديل قانون حماية المستهلك 2023.pdf",
    "قانون اتحادي 1 لسنة 2017 في  شأن مكافحة الإغراق (1).pdf",
    "قرار مجلس الوزراء  لسنة2012بتحرير الاغذية.pdf",
    "قرار مجلس الوزراء بشأن رسوم الخدمات التي تقدمها وزارة الاقتصاد الجديد (1).pdf",
    "قرار مجلس الوزراء بشأن رسوم الخدمات التي تقدمها وزارة الاقتصاد الجديد.pdf",
    "قرار مجلس الوزراء رقم 20 لسنة 2020 في شأن رسوم الخدمات التي تقدمها وزارة....pdf",
    "قرار مجلس الوزراء رقم 55 لسنة 2024 بشأن اللائحة التنفيذية للمرسوم بقانون اتحادي رقم 6 لسنة 2022 بشأن التعاونيات..pdf",
    "قرار مجلس الوزراء لسنة 2005 المواد الغذائية.pdf",
]


def find_pdf(name: str) -> Path | None:
    for d in DATA_DIRS:
        p = d / name
        if p.exists():
            return p
    return None


def ocr_pdf(pdf_path: Path, lang: str = "ara+eng") -> str:
    """Convert a scanned PDF to text using Tesseract OCR."""
    logger.info(f"  Converting pages to images: {pdf_path.name}")
    try:
        pages = convert_from_path(str(pdf_path), dpi=300)
    except Exception as e:
        raise RuntimeError(
            f"pdf2image failed for {pdf_path.name}: {e}\n"
            "Make sure poppler is installed and on PATH.\n"
            "  Windows: https://github.com/oschwartz10612/poppler-windows/releases/\n"
            "  Extract and add the bin/ folder to your system PATH."
        ) from e

    texts = []
    for i, page in enumerate(pages, 1):
        logger.info(f"    OCR page {i}/{len(pages)}…")
        text = pytesseract.image_to_string(page, lang=lang, config="--oem 3 --psm 3")
        texts.append(text)

    return "\n\n".join(texts)


def process_failing_pdfs() -> list[Path]:
    """OCR each known-failing PDF and write a .txt file next to it."""
    produced: list[Path] = []

    for name in KNOWN_FAILING:
        pdf_path = find_pdf(name)
        if pdf_path is None:
            logger.warning(f"  NOT FOUND — skipping: {name}")
            continue

        txt_path = pdf_path.with_suffix(".txt")
        if txt_path.exists():
            logger.info(f"  Already OCR'd (txt exists): {txt_path.name}")
            produced.append(txt_path)
            continue

        logger.info(f"Processing: {name}")
        try:
            text = ocr_pdf(pdf_path)
            if not text.strip():
                logger.warning(f"  OCR produced empty text for {name}. Check Tesseract Arabic pack.")
                continue
            txt_path.write_text(text, encoding="utf-8")
            logger.info(f"  Written: {txt_path}")
            produced.append(txt_path)
        except Exception as e:
            logger.error(f"  FAILED: {name} — {e}")

    return produced


async def reingest():
    """Re-run bulk_ingest to pick up the new .txt files."""
    logger.info("Re-ingesting documents via bulk_ingest…")
    # Import and run bulk_ingest's main logic directly
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)
    try:
        import bulk_ingest  # noqa: F401 — side-effect: runs ingest on import if __name__ == '__main__'
        # bulk_ingest exposes an async ingest function
        if hasattr(bulk_ingest, "main"):
            await bulk_ingest.main()
        elif hasattr(bulk_ingest, "ingest_documents"):
            await bulk_ingest.ingest_documents()
        else:
            logger.info("bulk_ingest has no callable async entry point — run it manually:")
            logger.info("  python bulk_ingest.py")
    except Exception as e:
        logger.error(f"Re-ingest error: {e}")
        logger.info("Run manually:  python bulk_ingest.py")


def main():
    logger.info("=" * 60)
    logger.info("OCR Batch Processor for Scanned Arabic PDFs")
    logger.info("=" * 60)

    # Verify Tesseract is available
    try:
        langs = pytesseract.get_languages(config="")
        if "ara" not in langs:
            logger.warning(
                "Tesseract Arabic language pack NOT found.\n"
                "Install it, then re-run this script.\n"
                "  Windows: Re-run the Tesseract installer and check 'Arabic' under language data."
            )
            sys.exit(1)
        logger.info(f"Tesseract OK. Available langs include: {', '.join(l for l in langs if l in ('ara','eng'))}")
    except Exception as e:
        logger.error(f"Tesseract not found or not on PATH: {e}")
        sys.exit(1)

    # Step 1: OCR
    produced = process_failing_pdfs()
    logger.info(f"\nOCR complete. Produced {len(produced)} text file(s).")

    if not produced:
        logger.warning("No text files produced. Check the paths and Tesseract installation.")
        return

    # Step 2: Re-ingest
    asyncio.run(reingest())

    logger.info("\nDone! Check /api/documents/stats — error_documents should decrease.")


if __name__ == "__main__":
    main()
