"""
PDF Template Analyzer using PyMuPDF (fitz).
Extracts page dimensions, fonts, margins, and structure from a reference PDF.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List


class TemplateAnalyzer:
    """
    Analyzes a reference PDF and extracts formatting configuration.
    
    Returns a template_config dict with:
    - page: width, height, unit
    - margins: top, bottom, left, right
    - fonts: heading, body, footer sizes/families
    - tables: detected table regions
    - sections: major document sections
    - confidence: extraction confidence 0–1
    """

    def analyze(self, pdf_path: str) -> Dict[str, Any]:
        """
        Analyze a PDF and return template config.
        Returns a dict with page, margins, fonts, tables, sections, confidence.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return self._fallback_config(pdf_path, error="PyMuPDF not installed")

        path = Path(pdf_path)
        if not path.exists():
            return self._fallback_config(pdf_path, error=f"File not found: {pdf_path}")

        try:
            doc = fitz.open(str(path))
        except Exception as e:
            return self._fallback_config(pdf_path, error=str(e))

        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return self._fallback_config(pdf_path, error="PDF has no pages")

        # Analyze first non-blank page for dimensions
        first_page = doc[0]
        page_dims = self._extract_page_dimensions(first_page)

        # Analyze fonts across pages
        fonts = self._extract_fonts(doc)

        # Analyze margins from first content page
        margins = self._extract_margins(first_page)

        # Detect sections from headings
        sections = self._detect_sections(doc)

        doc.close()

        confidence = self._calculate_confidence(page_dims, fonts, margins)

        return {
            "page": page_dims,
            "margins": margins,
            "fonts": fonts,
            "tables": [],
            "sections": sections,
            "confidence": confidence,
            "source": str(path.name),
            "page_count": page_count,
        }

    def _extract_page_dimensions(self, page) -> Dict[str, Any]:
        rect = page.rect
        return {
            "width": round(rect.width, 2),
            "height": round(rect.height, 2),
            "unit": "points",
        }

    def _extract_fonts(self, doc) -> Dict[str, Any]:
        font_sizes = []
        font_families = set()

        for page in doc:
            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:  # text block
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        font = span.get("font", "")
                        if size > 0:
                            font_sizes.append(size)
                        if font:
                            font_families.add(font)

        if not font_sizes:
            return {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            }

        sorted_sizes = sorted(set(font_sizes), reverse=True)
        primary_family = sorted(font_families)[0] if font_families else "Helvetica"

        fonts = {}
        if sorted_sizes:
            fonts["heading"] = {"family": primary_family, "size": round(sorted_sizes[0], 1)}
        if len(sorted_sizes) > 1:
            fonts["body"] = {"family": primary_family, "size": round(sorted_sizes[1], 1)}
        if len(sorted_sizes) > 2:
            fonts["footer"] = {"family": primary_family, "size": round(sorted_sizes[2], 1)}

        # Fallbacks
        fonts.setdefault("heading", {"family": "Helvetica-Bold", "size": 12})
        fonts.setdefault("body", {"family": "Helvetica", "size": 9})
        fonts.setdefault("footer", {"family": "Helvetica", "size": 8})

        return fonts

    def _extract_margins(self, page) -> Dict[str, float]:
        page_rect = page.rect
        blocks = page.get_text("dict", flags=0).get("blocks", [])

        x0_vals, y0_vals, x1_vals, y1_vals = [], [], [], []
        for block in blocks:
            if block.get("type") == 0:
                bbox = block.get("bbox", [])
                if len(bbox) == 4:
                    x0_vals.append(bbox[0])
                    y0_vals.append(bbox[1])
                    x1_vals.append(bbox[2])
                    y1_vals.append(bbox[3])

        if x0_vals:
            left = min(x0_vals)
            top = min(y0_vals)
            right = page_rect.width - max(x1_vals)
            bottom = page_rect.height - max(y1_vals)
        else:
            left = top = right = bottom = 72

        return {
            "top": round(max(top, 18), 2),
            "bottom": round(max(bottom, 18), 2),
            "left": round(max(left, 18), 2),
            "right": round(max(right, 18), 2),
        }

    def _detect_sections(self, doc) -> List[Dict[str, Any]]:
        """Detect major sections by looking for large bold text (headings)."""
        sections = []
        seen = set()

        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 0)
                        flags = span.get("flags", 0)
                        is_bold = bool(flags & 2**4)  # bold flag

                        if size >= 10 and is_bold and len(text) > 3 and text not in seen:
                            seen.add(text)
                            sections.append({
                                "name": text[:60],
                                "page": page_num,
                                "layout": "flow",
                            })

        # If no sections detected, use generic audit structure
        if not sections:
            page_count = len(doc)
            if page_count >= 1:
                sections.append({"name": "cover", "page": 1, "layout": "static"})
            if page_count >= 2:
                sections.append({"name": "financial_statements", "page": 2, "layout": "flow"})
            if page_count >= 4:
                sections.append({"name": "notes", "pages": list(range(4, page_count + 1)), "layout": "flow"})

        return sections

    def _calculate_confidence(self, page_dims: dict, fonts: dict, margins: dict) -> float:
        score = 0.0

        if page_dims.get("width", 0) > 0 and page_dims.get("height", 0) > 0:
            score += 0.4

        if fonts.get("body", {}).get("size", 0) > 0:
            score += 0.3

        if all(margins.get(k, 0) > 0 for k in ("top", "bottom", "left", "right")):
            score += 0.3

        return round(score, 2)

    def _fallback_config(self, pdf_path: str, error: str = "") -> Dict[str, Any]:
        return {
            "page": {"width": 612, "height": 792, "unit": "points"},
            "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [],
            "confidence": 0.0,
            "source": str(Path(pdf_path).name),
            "page_count": 0,
            "error": error,
        }
