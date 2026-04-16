"""
Prior Year Financial Data Extractor.

Strategy:
1. Extract text via PyMuPDF (works for digital PDFs).
2. Try regex table parsing (fast, no API cost).
3. Fall back to LLM text extraction if regex returns nothing.
4. Fall back to vision LLM (pdf2image) if text extraction fails entirely.
"""
import json
import logging
import re
import asyncio
from typing import Optional

from core.document_format_analyzer import analyze_audit_document

logger = logging.getLogger(__name__)


def _has_financial_data(text: str) -> bool:
    """Return True if text contains numeric patterns typical of financial statements."""
    if not text or not text.strip():
        return False
    return bool(re.search(r'\d{1,3}(?:,\d{3})+(?:\.\d{2})?', text))


def _fix_ocr_number(s: str) -> str:
    """Fix common OCR errors in financial numbers (e.g. S→5, l→1, O→0)."""
    # Fix character substitutions at start of digit groups
    s = re.sub(r'(?<![a-zA-Z])[Ss](?=,)', '5', s)
    s = re.sub(r'(?<![a-zA-Z])[lI](?=,)', '1', s)
    s = re.sub(r'(?<![a-zA-Z])[O](?=,)', '0', s)
    return s.strip()


def _parse_amount(raw: str) -> float:
    """
    Parse a financial amount string that may contain OCR noise.
    Handles: commas as thousands separators, parentheses for negatives,
    and OCR artifact where a period precedes 3 digits (also a thousands separator).
    """
    s = _fix_ocr_number(raw).replace(',', '').replace('(', '-').replace(')', '')
    # If "nnn.ddd" and ddd is exactly 3 digits → period is OCR'd comma (thousands separator)
    m = re.match(r'^(-?\d+)\.(\d{3})$', s)
    if m:
        s = m.group(1) + m.group(2)  # "5186.636" → "5186636"
    return float(s)


def _parse_text_tables(text: str) -> list[dict]:
    """
    Parse financial table rows from extracted PDF text.
    Tries multiple patterns to handle different PDF column layouts and OCR noise.
    """
    rows = []
    NUM = r'[\-\(]?[0-9SlO][0-9SlO,]*(?:\.[0-9SlO]+)?[\)]?'

    # Pattern 1: 2+ spaces between columns (original)
    pattern1 = re.compile(rf'^(.+?)\s{{2,}}({NUM})\s{{2,}}({NUM})\s*$')
    # Pattern 2: tab-separated
    pattern2 = re.compile(rf'^(.+?)\t({NUM})\t({NUM})\s*$')
    # Pattern 3: pipe-separated (some PDF extractors)
    pattern3 = re.compile(rf'^(.+?)\s*\|\s*({NUM})\s*\|\s*({NUM})\s*$')
    # Pattern 4: with optional note number between account name and values (OCR PDFs)
    # e.g. "Revenue 17 5,186,636 9,906,850" or "Revenue  17  S,186.636  9,906,850"
    pattern4 = re.compile(rf'^(.+?)\s+\d{{1,3}}\s+({NUM})\s+({NUM})\s*$')

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        for pattern in [pattern1, pattern2, pattern3, pattern4]:
            m = pattern.match(line)
            if m:
                account_name = m.group(1).strip()
                # Skip lines where account_name is just a number or note reference
                if re.match(r'^\d+$', account_name):
                    break
                try:
                    prior_value = _parse_amount(m.group(3))
                    cy_value = _parse_amount(m.group(2)) if m.group(2) else None
                    rows.append({
                        "account_name": account_name,
                        "prior_year_value": prior_value,
                        "current_year_value": cy_value,
                    })
                except ValueError:
                    pass
                break
    return rows


async def _extract_via_llm_text(text: str) -> list[dict]:
    """
    Use the LLM to parse financial figures from raw PDF text.
    This works for any PDF where text can be extracted but regex fails.
    """
    try:
        from core.llm_manager import get_llm_provider

        # Limit text to avoid token limits (keep most relevant financial section)
        text_to_send = text[:6000]

        prompt = (
            "The following is text extracted from a financial audit report. "
            "Extract all financial statement rows that have a prior year value. "
            "For each row output a JSON object: "
            "{\"account_name\": str, \"prior_year_value\": number}. "
            "The prior year column is typically the SECOND or RIGHTMOST numeric column. "
            "Ignore percentages and page numbers. "
            "Return ONLY a JSON array. No explanation.\n\n"
            f"EXTRACTED TEXT:\n{text_to_send}"
        )

        llm = get_llm_provider()
        resp = await llm.chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=3000)
        raw = resp.content.strip()

        # Strip markdown fences
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```\s*$', '', raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Find JSON array in response
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            raw = match.group(0)

        page_rows = json.loads(raw)
        if not isinstance(page_rows, list):
            return []

        result = []
        for r in page_rows:
            if not isinstance(r, dict):
                continue
            account = r.get("account_name", "")
            val = r.get("prior_year_value")
            if account and val is not None:
                try:
                    result.append({
                        "account_name": str(account),
                        "prior_year_value": float(val),
                    })
                except (ValueError, TypeError):
                    continue
        return result

    except Exception as exc:
        logger.error(f"LLM text extraction failed: {exc}")
        return []


async def _extract_via_vision(file_path: str) -> list[dict]:
    """
    Convert PDF pages to images and use Vision LLM to extract financial tables.
    Only attempted if pdf2image (poppler) is available.
    """
    try:
        from pdf2image import convert_from_path
        import base64
        import io
        from core.llm_manager import get_llm_provider

        pages = convert_from_path(file_path, first_page=1, last_page=8, dpi=150)
        llm = get_llm_provider()  # use active provider
        all_rows: list[dict] = []

        for page_img in pages[:4]:
            buf = io.BytesIO()
            page_img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This is a page from a financial audit report. "
                                "Extract all financial statement table rows as JSON. "
                                "For each row output: "
                                "{\"account_name\": str, \"prior_year_value\": number_or_null}. "
                                "The prior year column is the SECOND numeric column (rightmost). "
                                "Return ONLY a JSON array. No explanation."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ]

            resp = await llm.chat(messages, temperature=0.1, max_tokens=2000)
            raw = resp.content.strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)

            try:
                page_rows = json.loads(raw)
                if isinstance(page_rows, list):
                    for r in page_rows:
                        if isinstance(r, dict) and r.get("account_name") and r.get("prior_year_value") is not None:
                            all_rows.append({
                                "account_name": str(r["account_name"]),
                                "prior_year_value": float(r["prior_year_value"]) if r["prior_year_value"] else 0.0,
                            })
            except (json.JSONDecodeError, ValueError):
                continue

        seen = {}
        for r in all_rows:
            seen[r["account_name"].lower()] = r
        return list(seen.values())

    except ImportError:
        logger.warning("pdf2image not available — skipping vision fallback")
        return []
    except Exception as exc:
        logger.error(f"Vision extraction failed: {exc}")
        return []


async def _extract_via_fitz_vision(file_path: str) -> list[dict]:
    """
    Render PDF pages to images using fitz.get_pixmap() (no poppler needed),
    then send to the vision LLM to extract financial table rows.

    Sends up to 8 pages sampled across the full document. The first 2 pages
    of an audit report are typically the auditor's narrative and ToC — financial
    tables begin from page 3+, so we skip page 0 and sample the rest.
    """
    try:
        import fitz
        import base64
        from core.llm_manager import get_llm_provider

        doc = fitz.open(file_path)
        n = doc.page_count
        if n == 0:
            doc.close()
            return []

        logger.info(f"fitz vision: PDF has {n} pages")

        # Build a page index list that skips page 0 (cover/auditor letter)
        # and samples up to 8 pages spread across the document.
        # For a 30-page audit report this yields pages: 1,4,8,12,16,20,24,28
        if n <= 2:
            page_indices = list(range(n))
        else:
            # Always include page 1 (often ToC or first financial page)
            # then sample remaining pages evenly, skipping page 0
            remaining = list(range(1, n))
            max_pages = 8
            if len(remaining) <= max_pages:
                page_indices = remaining
            else:
                step = len(remaining) / max_pages
                page_indices = [remaining[int(i * step)] for i in range(max_pages)]

        logger.info(f"fitz vision: sending page indices {page_indices}")

        content_parts: list[dict] = [
            {
                "type": "text",
                "text": (
                    "These are pages from a financial audit report. "
                    "Extract every financial statement table row that has an account name "
                    "and a numeric amount. "
                    "The prior year column is the SECOND (rightmost) numeric column. "
                    "Ignore page numbers, percentages, and note references. "
                    "Return ONLY a valid JSON array with no explanation. "
                    "Each element: {\"account_name\": \"string\", \"prior_year_value\": number_or_null}"
                ),
            }
        ]

        for i in page_indices:
            # 1.5x scale (~110 dpi on A4) — sufficient for vision LLM, keeps payload manageable
            mat = fitz.Matrix(1.5, 1.5)
            pix = doc[i].get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })

        doc.close()

        llm = get_llm_provider()  # use active provider (nvidia/gemma-4 is vision-capable)
        resp = await llm.chat(
            [{"role": "user", "content": content_parts}],
            temperature=0.1,
            max_tokens=3000,
        )

        logger.info(f"fitz vision LLM response (first 200 chars): {resp.content[:200]}")

        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        page_rows = json.loads(raw)
        if not isinstance(page_rows, list):
            return []

        result = []
        for r in page_rows:
            if not isinstance(r, dict):
                continue
            account = r.get("account_name", "")
            val = r.get("prior_year_value")
            if account and val is not None:
                try:
                    result.append({
                        "account_name": str(account),
                        "prior_year_value": float(val),
                    })
                except (ValueError, TypeError):
                    continue

        logger.info(f"fitz vision extracted {len(result)} rows")
        seen: dict[str, dict] = {}
        for row in result:
            seen[row["account_name"].lower()] = row
        return list(seen.values())

    except ImportError:
        logger.warning("fitz (PyMuPDF) not available for vision extraction")
        return []
    except Exception as exc:
        import traceback
        logger.error(f"fitz vision extraction failed: {exc}\n{traceback.format_exc()}")
        return []


def build_prior_year_context(rows: list[dict]) -> str:
    """Format extracted rows as a readable context string for the LLM."""
    if not rows:
        return ""
    lines = ["Prior Year Financial Data (extracted from uploaded audit report):\n"]
    for r in rows:
        val = r.get("prior_year_value", 0)
        lines.append(f"  {r['account_name']}: AED {val:,.0f}")
    return "\n".join(lines)


async def extract_prior_year_from_pdf(file_path: str) -> dict:
    """
    Main entry point. Returns:
    {
        rows: list[{account_name, prior_year_value}],
        extraction_method: "text" | "llm_text" | "vision" | "failed",
        confidence: float,
        context: str
    }
    """
    # Extract structural template from PDF
    template = {}
    try:
        template = await analyze_audit_document(file_path)
    except Exception as exc:
        logger.warning(f"Template extraction failed (non-fatal): {exc}")

    all_text = ""

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        for page in doc:
            all_text += page.get_text()
        doc.close()
    except Exception as exc:
        logger.error(f"PyMuPDF text extraction failed: {exc}")

    if _has_financial_data(all_text):
        # Try regex parsing first
        rows = _parse_text_tables(all_text)
        if rows:
            return {
                "rows": rows,
                "extraction_method": "text",
                "confidence": 0.85,
                "context": build_prior_year_context(rows),
                "template": template,
            }

        # Regex failed — try LLM text parsing
        logger.info("Regex parsing returned 0 rows, trying LLM text extraction")
        rows = await _extract_via_llm_text(all_text)
        if rows:
            return {
                "rows": rows,
                "extraction_method": "llm_text",
                "confidence": 0.80,
                "context": build_prior_year_context(rows),
                "template": template,
            }

    # Stage 4: fitz pixmap → vision LLM (no poppler required)
    logger.info("Trying fitz vision extraction (pixmap → vision LLM)")
    rows = await _extract_via_fitz_vision(file_path)
    if rows:
        return {
            "rows": rows,
            "extraction_method": "vision",
            "confidence": 0.75,
            "context": build_prior_year_context(rows),
            "template": template,
        }

    # Stage 5: pdf2image fallback (only if poppler happens to be installed)
    rows = await _extract_via_vision(file_path)
    if rows:
        return {
            "rows": rows,
            "extraction_method": "vision_poppler",
            "confidence": 0.70,
            "context": build_prior_year_context(rows),
            "template": template,
        }

    logger.warning(f"All extraction methods failed for {file_path}")
    return {
        "rows": [],
        "extraction_method": "failed",
        "confidence": 0.0,
        "context": "",
        "template": template,
    }
