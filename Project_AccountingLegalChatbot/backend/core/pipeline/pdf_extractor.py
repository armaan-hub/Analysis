"""Stage 1: PDF text extraction with Arabic detection and OCR fallback."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ARABIC_RANGE_START = 0x0600
_ARABIC_RANGE_END   = 0x06FF
_ARABIC_THRESHOLD   = 0.30


@dataclass
class ExtractionResult:
    text:        str
    page_count:  int
    is_arabic:   bool
    skipped:     bool
    skip_reason: Optional[str]


def _is_arabic(text: str) -> bool:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    arabic_count = sum(
        1 for c in chars
        if _ARABIC_RANGE_START <= ord(c) <= _ARABIC_RANGE_END
    )
    return arabic_count / len(chars) > _ARABIC_THRESHOLD


def _ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="ara+eng")
    except ImportError:
        return ""
    except Exception as exc:
        logger.debug("OCR failed on page: %s", exc)
        return ""


def extract_text(path: str) -> ExtractionResult:
    import fitz
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in (".txt", ".csv"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return ExtractionResult(text=text, page_count=1, is_arabic=_is_arabic(text), skipped=False, skip_reason=None)
        except Exception as exc:
            return ExtractionResult("", 0, False, True, str(exc))

    if suffix == ".docx":
        try:
            import docx
            doc = docx.Document(str(p))
            text = "\n".join(para.text for para in doc.paragraphs)
            return ExtractionResult(text=text, page_count=1, is_arabic=_is_arabic(text), skipped=False, skip_reason=None)
        except ImportError:
            return ExtractionResult("", 0, False, True, "python-docx not installed")
        except Exception as exc:
            return ExtractionResult("", 0, False, True, str(exc))

    try:
        doc = fitz.open(str(p))
    except Exception as exc:
        return ExtractionResult("", 0, False, True, f"fitz.open failed: {exc}")

    try:
        if doc.is_encrypted:
            ok = doc.authenticate("")
            if not ok:
                return ExtractionResult("", 0, False, True, "encrypted PDF — blank password failed, skipping")

        pages_text: list[str] = []
        for page in doc:
            page_text = page.get_text()
            if not page_text.strip():
                page_text = _ocr_page(page)
            pages_text.append(page_text)

        full_text = "\n".join(pages_text)
        if not full_text.strip():
            return ExtractionResult("", doc.page_count, False, True, "no extractable text and OCR yielded nothing")

        return ExtractionResult(
            text=full_text,
            page_count=doc.page_count,
            is_arabic=_is_arabic(full_text),
            skipped=False,
            skip_reason=None,
        )
    finally:
        doc.close()
