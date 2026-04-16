"""
Document Format Analyzer — parses a prior year audit PDF and extracts
its full structural metadata as a template for report generation.

Uses PyMuPDF (fitz) for layout-aware text extraction with font size analysis.
Falls back to LLM-based structure extraction when heuristics are insufficient.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter
from typing import Any, Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ── Common audit section headings ─────────────────────────────────
_AUDIT_SECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"independent\s+auditor.?s?\s+report", re.IGNORECASE),
    re.compile(r"statement\s+of\s+financial\s+position", re.IGNORECASE),
    re.compile(r"statement\s+of\s+profit\s+(and|or)\s+loss", re.IGNORECASE),
    re.compile(r"statement\s+of\s+comprehensive\s+income", re.IGNORECASE),
    re.compile(r"statement\s+of\s+changes\s+in\s+equity", re.IGNORECASE),
    re.compile(r"statement\s+of\s+cash\s+flows?", re.IGNORECASE),
    re.compile(r"notes?\s+to\s+(the\s+)?financial\s+statements?", re.IGNORECASE),
    re.compile(r"balance\s+sheet", re.IGNORECASE),
    re.compile(r"income\s+statement", re.IGNORECASE),
]

_CURRENCY_PATTERNS = re.compile(
    r"\b(AED|USD|INR|EUR|GBP|SAR|QAR|BHD|OMR|KWD|EGP|PKR|BDT|LKR|NPR|"
    r"JPY|CNY|SGD|MYR|THB|IDR|PHP|AUD|NZD|CAD|CHF|SEK|NOK|DKK|ZAR|BRL|"
    r"KES|NGN|GHS|TZS|UGX)\b"
)

_NUMBER_PATTERN = re.compile(r"[\d,]+(?:\.\d+)?")
_PARENTHETICAL_NEGATIVE = re.compile(r"\([\d,]+(?:\.\d+)?\)")
_DASH_NEGATIVE = re.compile(r"-[\d,]+(?:\.\d+)?")


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

async def analyze_audit_document(file_path: str) -> dict:
    """
    Extract structural template from a prior year audit PDF.

    Returns a dict matching the documented schema with keys:
    document_structure, account_grouping, terminology, formatting_rules.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", file_path, exc)
        return _empty_result()

    if doc.page_count == 0:
        doc.close()
        return _empty_result()

    # Step 1: extract all text blocks with font metadata
    page_blocks = _extract_page_blocks(doc)
    full_text = "\n".join(
        blk["text"] for page in page_blocks for blk in page
    )

    if not full_text.strip():
        actual_pages = doc.page_count
        doc.close()
        logger.info(f"Scanned PDF detected (no text layer) — using vision LLM for template extraction")
        result = await _analyze_via_vision(file_path)
        result["document_structure"]["pages"] = actual_pages
        return result

    # Step 2: determine font-size thresholds
    font_stats = _compute_font_stats(page_blocks)

    # Step 3: detect sections from headings
    sections = _detect_sections(page_blocks, font_stats, doc.page_count)

    # Step 4: if heuristic found too few sections, try LLM fallback
    if len(sections) < 2:
        llm_sections = await _llm_section_fallback(full_text)
        if llm_sections and len(llm_sections) > len(sections):
            sections = llm_sections

    # Step 5: extract document-level metadata
    meta = _extract_metadata(full_text, doc)

    # Step 6: account grouping
    account_grouping = _extract_account_grouping(page_blocks, sections, font_stats)

    # Step 7: terminology
    terminology = _extract_terminology(full_text, sections)

    # Step 8: formatting rules
    formatting_rules = _extract_formatting_rules(full_text, page_blocks, font_stats)

    doc.close()

    return {
        "document_structure": {
            "title": meta["title"],
            "date_range": meta["date_range"],
            "company_name": meta["company_name"],
            "auditor_name": meta["auditor_name"],
            "pages": meta["pages"],
            "sections": sections,
        },
        "account_grouping": account_grouping,
        "terminology": terminology,
        "formatting_rules": formatting_rules,
    }


# ═══════════════════════════════════════════════════════════════════
# Text extraction helpers
# ═══════════════════════════════════════════════════════════════════

def _extract_page_blocks(doc: fitz.Document) -> list[list[dict]]:
    """Extract text blocks per page with font metadata."""
    all_pages: list[list[dict]] = []

    for page_idx, page in enumerate(doc):
        blocks: list[dict] = []
        page_height = page.rect.height

        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # text block only
                continue
            for line in block.get("lines", []):
                line_text_parts = []
                font_sizes = []
                is_bold = False
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if txt.strip():
                        line_text_parts.append(txt)
                        font_sizes.append(span.get("size", 10.0))
                        flags = span.get("flags", 0)
                        if flags & 2 ** 4:  # bold flag
                            is_bold = True

                line_text = "".join(line_text_parts).strip()
                if not line_text:
                    continue

                avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0
                y_pos = line.get("bbox", [0, 0, 0, 0])[1]
                x_pos = line.get("bbox", [0, 0, 0, 0])[0]

                # Determine vertical position on page
                rel_y = y_pos / page_height if page_height > 0 else 0.5
                if rel_y < 0.33:
                    estimated_position = "top"
                elif rel_y < 0.66:
                    estimated_position = "middle"
                else:
                    estimated_position = "bottom"

                blocks.append({
                    "text": line_text,
                    "font_size": round(avg_font, 1),
                    "is_bold": is_bold,
                    "x": round(x_pos, 1),
                    "y": round(y_pos, 1),
                    "page": page_idx,
                    "estimated_position": estimated_position,
                })

        all_pages.append(blocks)
    return all_pages


def _compute_font_stats(page_blocks: list[list[dict]]) -> dict:
    """Compute font-size statistics to classify text roles."""
    sizes: list[float] = []
    for page in page_blocks:
        for blk in page:
            sizes.append(blk["font_size"])

    if not sizes:
        return {"body": 10.0, "heading_min": 12.0, "subheading_min": 11.0}

    size_counter = Counter(round(s, 0) for s in sizes)
    max_count = size_counter.most_common(1)[0][1]
    # When multiple sizes tie for most frequent, pick the smallest (body text)
    tied = [s for s, c in size_counter.items() if c == max_count]
    body_size = min(tied)

    unique_sizes = sorted(set(round(s, 0) for s in sizes), reverse=True)

    heading_min = body_size + 2
    subheading_min = body_size + 1

    # If there are sizes larger than body, use them
    larger = [s for s in unique_sizes if s > body_size]
    if len(larger) >= 2:
        heading_min = larger[1]  # second largest for sub-headings
        subheading_min = min(larger)
    elif len(larger) == 1:
        heading_min = larger[0]
        subheading_min = larger[0]

    return {
        "body": body_size,
        "heading_min": heading_min,
        "subheading_min": subheading_min,
        "all_sizes": unique_sizes,
    }


def _detect_sections(
    page_blocks: list[list[dict]], font_stats: dict, total_pages: int
) -> list[dict]:
    """Detect section headings by font size, boldness, and pattern matching."""
    sections: list[dict] = []
    body_size = font_stats["body"]

    for page_idx, page in enumerate(page_blocks):
        for blk in page:
            text = blk["text"].strip()
            if not text or len(text) < 3:
                continue

            is_heading = False
            level = 3
            content_type = "heading"

            # Check for known audit section patterns
            matched_pattern = any(p.search(text) for p in _AUDIT_SECTION_PATTERNS)

            # Font-size based detection
            font_size = blk["font_size"]
            if font_size > body_size + 3:
                is_heading = True
                level = 1
            elif font_size > body_size + 1:
                is_heading = True
                level = 2
            elif font_size > body_size:
                is_heading = True
                level = 3

            # Bold + uppercase heuristic
            if blk["is_bold"] and text.isupper() and len(text) < 80:
                is_heading = True
                if level > 2:
                    level = 2

            # Pattern match overrides
            if matched_pattern:
                is_heading = True
                if level > 2:
                    level = 1

            # All-caps short lines are likely headings
            if text.isupper() and len(text) < 60 and not _NUMBER_PATTERN.search(text):
                is_heading = True
                if level > 2:
                    level = 2

            if not is_heading:
                continue

            # Detect table structure if next lines have numbers
            table_structure = _detect_table_after_heading(
                page_blocks, page_idx, blk["y"]
            )

            sections.append({
                "section_id": str(uuid.uuid4()),
                "title": text,
                "level": level,
                "start_page": page_idx + 1,
                "estimated_position": blk["estimated_position"],
                "content_type": "table" if table_structure else content_type,
                "table_structure": table_structure,
            })

    return sections


def _detect_table_after_heading(
    page_blocks: list[list[dict]], page_idx: int, heading_y: float
) -> Optional[dict]:
    """Check if the content after a heading looks like a table."""
    if page_idx >= len(page_blocks):
        return None

    page = page_blocks[page_idx]
    rows_with_numbers = []
    header_candidate = None

    for blk in page:
        if blk["y"] <= heading_y:
            continue
        text = blk["text"].strip()
        if not text:
            continue

        has_numbers = bool(_NUMBER_PATTERN.search(text))
        if has_numbers:
            rows_with_numbers.append(blk)
        elif not header_candidate and not has_numbers and len(rows_with_numbers) == 0:
            header_candidate = blk

        if len(rows_with_numbers) >= 3:
            break

    if len(rows_with_numbers) < 2:
        return None

    # Try to extract column structure from header or first row
    columns = []
    if header_candidate:
        columns = [c.strip() for c in re.split(r"\s{2,}|\t", header_candidate["text"]) if c.strip()]

    column_count = max(len(columns), 2)
    alignments = ["left"] + ["right"] * (column_count - 1)

    # Detect indentation levels from row x-positions
    x_positions = sorted(set(round(r["x"]) for r in rows_with_numbers))
    indent_levels = min(len(x_positions), 3)

    return {
        "columns": columns,
        "column_count": column_count,
        "alignment": alignments,
        "indentation_levels": indent_levels,
    }


# ═══════════════════════════════════════════════════════════════════
# Metadata extraction
# ═══════════════════════════════════════════════════════════════════

def _extract_metadata(full_text: str, doc: fitz.Document) -> dict:
    """Extract document-level metadata: title, dates, company, auditor."""
    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]

    # Title: typically first non-empty line or PDF metadata
    title = doc.metadata.get("title", "") if doc.metadata else ""
    if not title and lines:
        title = lines[0]

    # Company name: look for LLC, Ltd, Co., etc. in first few lines
    company_name = ""
    company_re = re.compile(
        r"(.{3,60}(?:LLC|L\.L\.C|Ltd|Limited|Corp|Inc|Co\.|Company|PJSC|FZE|FZC|FZCO)\.?)",
        re.IGNORECASE,
    )
    for line in lines[:15]:
        m = company_re.search(line)
        if m:
            company_name = m.group(1).strip()
            break
    if not company_name and lines:
        company_name = lines[0]

    # Date range
    date_range = ""
    date_re = re.compile(
        r"(?:for\s+the\s+)?(?:year|period)\s+ended?\s+.{5,40}",
        re.IGNORECASE,
    )
    for line in lines[:30]:
        m = date_re.search(line)
        if m:
            date_range = m.group(0).strip()
            break
    if not date_range:
        date_match = re.search(
            r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+\d{4}",
            full_text[:2000],
        )
        if date_match:
            date_range = date_match.group(0)

    # Auditor name
    auditor_name = ""
    auditor_re = re.compile(
        r"((?:Deloitte|KPMG|PwC|PricewaterhouseCoopers|Ernst\s*&\s*Young|EY|"
        r"Grant\s+Thornton|BDO|Mazars|RSM|Moore|Crowe|Baker\s+Tilly|"
        r"MHA|PKF|Nexia|HLB|Kreston|UHY)[\w\s&.,]*)",
        re.IGNORECASE,
    )
    m = auditor_re.search(full_text[:5000])
    if m:
        auditor_name = m.group(1).strip()

    return {
        "title": title,
        "date_range": date_range,
        "company_name": company_name,
        "auditor_name": auditor_name,
        "pages": doc.page_count,
    }


# ═══════════════════════════════════════════════════════════════════
# Account grouping
# ═══════════════════════════════════════════════════════════════════

def _extract_account_grouping(
    page_blocks: list[list[dict]],
    sections: list[dict],
    font_stats: dict,
) -> dict[str, list[dict]]:
    """Group account line items under their section headings."""
    grouping: dict[str, list[dict]] = {}
    body_size = font_stats["body"]

    # Build a flat list of all blocks with page info
    flat_blocks = []
    for page in page_blocks:
        for blk in page:
            flat_blocks.append(blk)

    if not flat_blocks:
        return grouping

    # Compute base indentation (minimum x across body-sized text)
    body_x_values = [b["x"] for b in flat_blocks if abs(b["font_size"] - body_size) < 1]
    base_x = min(body_x_values) if body_x_values else 72.0

    # For each section that has table content, collect account rows
    for section in sections:
        if section.get("content_type") not in ("table", "heading"):
            continue

        section_title = section["title"]
        section_page = section["start_page"] - 1  # 0-based
        accounts: list[dict] = []

        # Find blocks on the same page after the section heading
        collecting = False
        for blk in flat_blocks:
            if blk["page"] < section_page:
                continue
            if blk["page"] > section_page + 1:
                break

            text = blk["text"].strip()
            if text == section_title:
                collecting = True
                continue

            if not collecting:
                continue

            # Stop if we hit another heading
            if blk["font_size"] > body_size + 1 and not _NUMBER_PATTERN.search(text):
                break

            # Parse account rows: lines containing numbers
            has_numbers = bool(_NUMBER_PATTERN.search(text))
            if not has_numbers and len(text) < 5:
                continue

            # Calculate indent level
            x_offset = blk["x"] - base_x
            indent_level = 0
            if x_offset > 30:
                indent_level = 2
            elif x_offset > 10:
                indent_level = 1

            # Extract account name (text before numbers)
            account_name = re.split(r"\s{2,}|\t", text)[0].strip()
            if not account_name:
                continue

            # Try to find account code (e.g., "Note 5" or a numeric code)
            code_match = re.search(r"\b(?:Note\s+)?(\d{1,6})\b", text)
            account_code = code_match.group(0) if code_match and not has_numbers else None
            # Don't treat amounts as codes
            if account_code and len(account_code) > 3:
                account_code = None

            is_total = bool(re.search(r"\btotal\b", text, re.IGNORECASE))
            is_subtotal = bool(re.search(r"\bsub[\s-]?total\b", text, re.IGNORECASE))

            # Bold lines with numbers may also be totals
            if blk["is_bold"] and has_numbers and not is_subtotal:
                is_total = True

            accounts.append({
                "account_name": account_name,
                "account_code": account_code,
                "indent_level": indent_level,
                "is_subtotal": is_subtotal,
                "is_total": is_total,
            })

        if accounts:
            grouping[section_title] = accounts

    return grouping


# ═══════════════════════════════════════════════════════════════════
# Terminology
# ═══════════════════════════════════════════════════════════════════

def _extract_terminology(full_text: str, sections: list[dict]) -> dict:
    """Extract headings, common phrases, and currency."""
    headings_seen = [s["title"] for s in sections]

    # Common financial phrases
    phrase_patterns = [
        r"as at \d",
        r"for the year ended",
        r"for the period ended",
        r"in accordance with",
        r"going concern",
        r"true and fair view",
        r"material misstatement",
        r"significant accounting policies",
        r"related party",
        r"contingent liabilit",
        r"fair value",
        r"impairment",
        r"depreciation",
        r"amortization",
        r"revenue recognition",
        r"financial instruments",
        r"lease",
        r"provisions",
    ]
    common_phrases = []
    for pat in phrase_patterns:
        if re.search(pat, full_text, re.IGNORECASE):
            common_phrases.append(pat.replace(r"\d", "").strip())

    # Currency detection
    currency = "USD"  # default
    currency_matches = _CURRENCY_PATTERNS.findall(full_text)
    if currency_matches:
        currency_counter = Counter(currency_matches)
        currency = currency_counter.most_common(1)[0][0]

    return {
        "headings_seen": headings_seen,
        "common_phrases": common_phrases,
        "currency": currency,
    }


# ═══════════════════════════════════════════════════════════════════
# Formatting rules
# ═══════════════════════════════════════════════════════════════════

def _extract_formatting_rules(
    full_text: str,
    page_blocks: list[list[dict]],
    font_stats: dict,
) -> dict:
    """Detect formatting rules: currency format, negative numbers, font hierarchy."""
    # Negative number format
    paren_count = len(_PARENTHETICAL_NEGATIVE.findall(full_text))
    dash_count = len(_DASH_NEGATIVE.findall(full_text))
    if paren_count >= dash_count:
        negative_format = "(X,XXX)" if paren_count > 0 else "N/A"
    else:
        negative_format = "-X,XXX"

    # Currency format detection
    # Look for patterns like "AED 1,234" or "1,234.56"
    has_thousands_sep = bool(re.search(r"\d{1,3},\d{3}", full_text))
    has_decimal = bool(re.search(r"\d+\.\d{2}", full_text))
    if has_thousands_sep and has_decimal:
        currency_format = "#,##0.00"
    elif has_thousands_sep:
        currency_format = "#,##0"
    else:
        currency_format = "#0"

    # Detect which sections might have page breaks
    page_break_sections: list[str] = []
    # A section at the top of a new page (after page 1) likely has a page break before it
    for page_idx, page in enumerate(page_blocks):
        if page_idx == 0:
            continue
        for blk in page[:3]:  # first few blocks on the page
            if blk["font_size"] > font_stats["body"] + 1:
                page_break_sections.append(blk["text"].strip())
                break

    # Font hierarchy detection
    heading_bold = False
    table_header_bold = False
    for page in page_blocks:
        for blk in page:
            if blk["font_size"] > font_stats["body"] + 1 and blk["is_bold"]:
                heading_bold = True
            # Table headers: bold text at body size before numeric rows
            if abs(blk["font_size"] - font_stats["body"]) < 1 and blk["is_bold"]:
                table_header_bold = True

    return {
        "page_break_after_sections": page_break_sections,
        "table_formatting": {
            "currency_format": currency_format,
            "negative_number_format": negative_format,
        },
        "font_hierarchy": {
            "heading_1_bold": heading_bold,
            "table_header_bold": table_header_bold,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# LLM fallback
# ═══════════════════════════════════════════════════════════════════

async def _llm_section_fallback(full_text: str) -> list[dict]:
    """Use LLM to extract section structure when heuristics fail."""
    try:
        from core.llm_manager import get_llm_provider
    except ImportError:
        logger.warning("LLM manager not available for fallback")
        return []

    # Truncate text to avoid token limits
    truncated = full_text[:8000]

    prompt = (
        "You are analyzing a financial audit document. Extract the section headings "
        "and their hierarchy. Return ONLY a JSON array where each element has:\n"
        '  {"title": "...", "level": 1|2|3, "content_type": "heading"|"table"|"narrative"}\n\n'
        "Level 1 = major sections (e.g., financial statements), "
        "Level 2 = sub-sections, Level 3 = minor headings.\n\n"
        f"Document text:\n{truncated}"
    )

    try:
        llm = get_llm_provider()
        resp = await llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000,
        )

        # Parse JSON from response
        content = resp.content.strip()
        # Try to find JSON array in the response
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            raw_sections = json.loads(json_match.group(0))
        else:
            raw_sections = json.loads(content)

        sections = []
        for item in raw_sections:
            sections.append({
                "section_id": str(uuid.uuid4()),
                "title": item.get("title", ""),
                "level": item.get("level", 1),
                "start_page": 1,
                "estimated_position": "top",
                "content_type": item.get("content_type", "heading"),
                "table_structure": None,
            })
        return sections
    except Exception as exc:
        logger.warning("LLM section fallback failed: %s", exc)
        return []


# ═══════════════════════════════════════════════════════════════════
# Vision-based analysis for scanned PDFs
# ═══════════════════════════════════════════════════════════════════

async def _analyze_via_vision(file_path: str) -> dict:
    """
    For scanned PDFs where text extraction yields nothing.
    Renders pages via fitz pixmap and sends to vision LLM to extract structure.
    """
    try:
        import base64
        from core.llm_manager import get_llm_provider

        doc = fitz.open(file_path)
        actual_pages = doc.page_count

        content_parts: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Analyze these pages from a financial audit report PDF. "
                    "Return ONLY valid JSON (no explanation) with this exact structure:\n"
                    "{\n"
                    '  "document_structure": {\n'
                    '    "title": "string",\n'
                    '    "date_range": "string",\n'
                    '    "company_name": "string",\n'
                    '    "auditor_name": "string or empty",\n'
                    '    "sections": [\n'
                    '      {"title": "string", "level": 1, "content_type": "table or narrative"}\n'
                    "    ]\n"
                    "  },\n"
                    '  "account_grouping": {},\n'
                    '  "terminology": {"currency": "AED or USD", "common_phrases": [], "headings_seen": []},\n'
                    '  "formatting_rules": {\n'
                    '    "table_formatting": {"currency_format": "#,##0 or #,##0.00", "negative_number_format": "(X,XXX) or -X,XXX"},\n'
                    '    "font_hierarchy": {"heading_1_bold": true, "table_header_bold": true},\n'
                    '    "page_break_after_sections": []\n'
                    "  }\n"
                    "}"
                ),
            }
        ]

        for i in range(min(6, actual_pages)):
            mat = fitz.Matrix(2, 2)
            pix = doc[i].get_pixmap(matrix=mat)
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })

        doc.close()

        llm = get_llm_provider("openai")
        resp = await llm.chat(
            [{"role": "user", "content": content_parts}],
            temperature=0.1,
            max_tokens=3000,
        )

        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        result = json.loads(raw)

        for s in result.get("document_structure", {}).get("sections", []):
            if "section_id" not in s:
                s["section_id"] = str(uuid.uuid4())
            if "start_page" not in s:
                s["start_page"] = 1
            if "estimated_position" not in s:
                s["estimated_position"] = "top"
            if "table_structure" not in s:
                s["table_structure"] = None

        result["document_structure"]["pages"] = actual_pages
        return result

    except Exception as exc:
        logger.error(f"Vision template analysis failed: {exc}")
        empty = _empty_result()
        try:
            doc2 = fitz.open(file_path)
            empty["document_structure"]["pages"] = doc2.page_count
            doc2.close()
        except Exception:
            pass
        return empty


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _empty_result() -> dict:
    """Return a valid but empty analysis result."""
    return {
        "document_structure": {
            "title": "",
            "date_range": "",
            "company_name": "",
            "auditor_name": "",
            "pages": 0,
            "sections": [],
        },
        "account_grouping": {},
        "terminology": {
            "headings_seen": [],
            "common_phrases": [],
            "currency": "USD",
        },
        "formatting_rules": {
            "page_break_after_sections": [],
            "table_formatting": {
                "currency_format": "#,##0",
                "negative_number_format": "N/A",
            },
            "font_hierarchy": {
                "heading_1_bold": False,
                "table_header_bold": False,
            },
        },
    }
