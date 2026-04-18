"""
FormatFingerprinter — Phase 1 of the fast format learning pipeline.

Computes a lightweight 6-field fingerprint from the first 3 pages of a PDF
and matches it against the prebuilt format library to decide whether full
extraction is needed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.document_format_analyzer import _AUDIT_SECTION_PATTERNS, _CURRENCY_PATTERNS
from core.prebuilt_formats import PREBUILT_FORMATS

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
_PAGE_SIZE_TOLERANCE = 5.0  # points


def _detect_page_size(width: float, height: float) -> str:
    if abs(width - 595.28) < _PAGE_SIZE_TOLERANCE and abs(height - 841.89) < _PAGE_SIZE_TOLERANCE:
        return "A4"
    if abs(width - 612.0) < _PAGE_SIZE_TOLERANCE and abs(height - 792.0) < _PAGE_SIZE_TOLERANCE:
        return "US_LETTER"
    return "CUSTOM"


class FormatFingerprinter:
    """Compute a format fingerprint and match it against the prebuilt library."""

    MATCH_THRESHOLD = 88

    def fingerprint(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract a 6-field fingerprint from the first 3 pages of the PDF.
        Returns the fingerprint schema even on error (with default values).
        """
        default = {
            "page_size": "CUSTOM",
            "currency": "unknown",
            "section_count": 0,
            "has_notes": False,
            "col_count": 2,
            "format_family": "unknown",
        }

        try:
            import fitz
        except ImportError:
            return default

        path = Path(pdf_path)
        if not path.exists():
            return default

        try:
            doc = fitz.open(str(path))
        except Exception:
            return default

        if len(doc) == 0:
            doc.close()
            return default

        pages_to_scan = list(doc)[:min(3, len(doc))]

        # Page size from first page
        rect = doc[0].rect
        page_size = _detect_page_size(rect.width, rect.height)

        full_text = " ".join(
            span.get("text", "")
            for page in pages_to_scan
            for block in page.get_text("dict", flags=0).get("blocks", [])
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )

        # Currency detection
        currency_match = _CURRENCY_PATTERNS.search(full_text)
        currency = currency_match.group(0) if currency_match else "unknown"

        # Extended currency scan: if not found in first 3 pages, scan up to page 10
        if currency == "unknown" and len(doc) > 3:
            for extra_page in list(doc)[3:min(10, len(doc))]:
                extra_text = extra_page.get_text()
                extra_match = _CURRENCY_PATTERNS.search(extra_text)
                if extra_match:
                    currency = extra_match.group(0)
                    break

        # Section count
        section_count = sum(
            1 for pattern in _AUDIT_SECTION_PATTERNS if pattern.search(full_text)
        )

        # Notes detection
        has_notes = bool(re.search(r"notes?\s+to\s+(the\s+)?financial", full_text, re.IGNORECASE))

        # Column count: count distinct year headers
        years_found = set(_YEAR_PATTERN.findall(full_text))
        col_count = min(len(years_found) + 1, 3) if years_found else 2

        # Format family heuristic
        if re.search(r"\bifrs\b", full_text, re.IGNORECASE):
            format_family = "IFRS"
        elif re.search(r"\bgaap\b", full_text, re.IGNORECASE):
            format_family = "GAAP"
        elif re.search(r"\btax\b", full_text, re.IGNORECASE):
            format_family = "local-tax"
        else:
            format_family = "IFRS"  # Default for UAE/GCC audits

        doc.close()

        return {
            "page_size": page_size,
            "currency": currency,
            "section_count": section_count,
            "has_notes": has_notes,
            "col_count": col_count,
            "format_family": format_family,
        }

    def _score(self, fp: Dict[str, Any], candidate: Dict[str, Any]) -> int:
        """
        Compute similarity score 0-100 between two fingerprints.

        Scoring weights:
          page_size     30
          currency      25
          format_family 20
          section_count 15  (within +/-1)
          col_count     10
        """
        score = 0
        fp_ps = fp.get("page_size")
        cand_ps = candidate.get("page_size")
        if fp_ps == cand_ps:
            score += 30
        elif fp_ps in (candidate.get("page_size_alts") or []):
            score += 30
        if fp.get("currency") == candidate.get("currency"):
            score += 25
        if fp.get("format_family") == candidate.get("format_family"):
            score += 20
        if abs(fp.get("section_count", 0) - candidate.get("section_count", 0)) <= 1:
            score += 15
        if fp.get("col_count") == candidate.get("col_count"):
            score += 10
        return score

    def match(
        self,
        pdf_path: str,
        user_templates: Optional[list] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """
        Match the PDF against the prebuilt library (+ optional user templates).

        Returns (best_config, best_score, source_id).
        source_id is None when best_score < MATCH_THRESHOLD.
        """
        fp = self.fingerprint(pdf_path)
        best_score = 0
        best_config: Optional[Dict[str, Any]] = None
        best_id: Optional[str] = None

        candidates = list(PREBUILT_FORMATS)
        if user_templates:
            candidates.extend(user_templates)

        for entry in candidates:
            candidate_fp = entry.get("fingerprint")
            if candidate_fp is None:
                continue
            score = self._score(fp, candidate_fp)
            if score > best_score:
                best_score = score
                best_config = entry.get("config")
                best_id = entry.get("id")

        if best_score >= self.MATCH_THRESHOLD:
            return best_config, best_score, best_id
        return None, best_score, None
