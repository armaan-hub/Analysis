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

    def analyze_precise(self, pdf_path: str) -> Dict[str, Any]:
        """
        High-precision PDF analysis.
        Returns the same schema as analyze() plus 'columns' and 'spacing' fields,
        and uses role-based font mapping instead of size-sorted font mapping.
        """
        try:
            import fitz
        except ImportError:
            result = self._fallback_config(pdf_path, error="PyMuPDF not installed")
            result["columns"] = self._fallback_columns(None, None)
            result["spacing"] = self._fallback_spacing()
            return result

        path = Path(pdf_path)
        if not path.exists():
            result = self._fallback_config(pdf_path, error=f"File not found: {pdf_path}")
            result["columns"] = self._fallback_columns(None, None)
            result["spacing"] = self._fallback_spacing()
            return result

        try:
            doc = fitz.open(str(path))
        except Exception as e:
            result = self._fallback_config(pdf_path, error=str(e))
            result["columns"] = self._fallback_columns(None, None)
            result["spacing"] = self._fallback_spacing()
            return result

        page_count = len(doc)
        if page_count == 0:
            doc.close()
            result = self._fallback_config(pdf_path, error="PDF has no pages")
            result["columns"] = self._fallback_columns(None, None)
            result["spacing"] = self._fallback_spacing()
            return result

        first_page = doc[0]
        page_dims = self._extract_page_dimensions(first_page)
        margins = self._extract_margins(first_page)
        sections = self._detect_sections(doc)

        analysis_pages = [doc[i] for i in range(min(4, page_count))]
        columns = self._extract_columns(analysis_pages, page_dims, margins)
        spacing = self._extract_spacing(analysis_pages)
        fonts = self._extract_font_roles(doc)

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
            "columns": columns,
            "spacing": spacing,
        }

    def _kmeans_1d(self, values: list, k: int, max_iter: int = 20) -> list:
        """Simple 1D k-means. Returns list of k sorted centroids."""
        import numpy as np
        arr = np.array(values, dtype=float)
        indices = np.round(np.linspace(0, len(arr) - 1, k)).astype(int)
        centroids = np.sort(arr)[indices].astype(float)
        for _ in range(max_iter):
            dists = np.abs(arr[:, None] - centroids[None, :])
            labels = np.argmin(dists, axis=1)
            new_centroids = np.array([
                arr[labels == i].mean() if (labels == i).any() else centroids[i]
                for i in range(k)
            ])
            if np.allclose(centroids, new_centroids, atol=0.5):
                break
            centroids = new_centroids
        return sorted(centroids.tolist())

    def _fallback_columns(self, page_dims, margins) -> Dict[str, float]:
        """Return column positions based on standard A4 proportions."""
        w = page_dims.get("width", 595.28) if page_dims else 595.28
        left = margins.get("left", 72) if margins else 72
        return {
            "label_col_x": round(left, 2),
            "notes_col_x": round(w * 0.52, 2),
            "year1_col_x": round(w * 0.65, 2),
            "year2_col_x": round(w * 0.80, 2),
            "currency_label_y": 0.0,
        }

    def _fallback_spacing(self) -> Dict[str, float]:
        return {
            "heading_after": 18.0,
            "row_height": 14.0,
            "section_gap": 24.0,
            "subtotal_gap": 6.0,
            "indent_level_1": 90.0,
            "indent_level_2": 108.0,
        }

    def _extract_columns(self, pages: list, page_dims: Dict, margins: Dict) -> Dict[str, float]:
        """
        Detect data column x-positions using 1D k-means on numeric span x0 values.
        Falls back to page-width proportions if fewer than 10 numeric spans are found.
        """
        import re
        import numpy as np

        _NUMERIC_RE = re.compile(r"^[\s\d,.()–\-]+$")
        numeric_x0s: List[float] = []

        for page in pages:
            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if len(text) >= 2 and _NUMERIC_RE.match(text):
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            numeric_x0s.append(float(bbox[0]))

        if len(numeric_x0s) < 10:
            return self._fallback_columns(page_dims, margins)

        page_width = page_dims.get("width", 595.28)
        x_range = max(numeric_x0s) - min(numeric_x0s)
        k = 3 if x_range > page_width * 0.35 else 2
        centroids = self._kmeans_1d(numeric_x0s, k)

        left = margins.get("left", 72)
        result: Dict[str, float] = {
            "label_col_x": round(float(left), 2),
            "notes_col_x": 0.0,
            "year1_col_x": round(centroids[-2] if k >= 2 else centroids[0], 2),
            "year2_col_x": round(centroids[-1], 2),
            "currency_label_y": 0.0,
        }
        if k >= 3:
            result["notes_col_x"] = round(centroids[0], 2)

        return result

    def _extract_spacing(self, pages: list) -> Dict[str, float]:
        """
        Detect line spacing by measuring y-gaps between consecutive spans.
        Groups gaps into small/medium/large via quantile split.
        """
        import numpy as np

        y0_by_page: List[float] = []

        for page in pages:
            line_y0s: List[float] = []
            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    bbox = line.get("bbox", [0, 0, 0, 0])
                    line_y0s.append(float(bbox[1]))
            if line_y0s:
                y0_by_page.extend(sorted(line_y0s))

        if len(y0_by_page) < 4:
            return self._fallback_spacing()

        # Deduplicate close y-values (spans on same line) by rounding to 1 pt
        rounded = sorted(set(round(y, 1) for y in y0_by_page))
        arr = np.array(rounded, dtype=float)
        gaps = np.diff(arr)
        gaps = gaps[gaps > 1.5]

        if len(gaps) < 3:
            return self._fallback_spacing()

        q33 = float(np.percentile(gaps, 33))
        q67 = float(np.percentile(gaps, 67))
        medium = gaps[(gaps > q33) & (gaps <= q67)]
        large = gaps[gaps > q67]

        row_height = float(np.median(medium)) if len(medium) > 0 else float(np.median(gaps))
        section_gap = float(np.median(large)) if len(large) > 0 else row_height * 2.0

        label_x0s: List[float] = []
        for page in pages:
            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text and not text.replace(",", "").replace(".", "").replace("-", "").replace("(", "").replace(")", "").isdigit():
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            label_x0s.append(round(float(bbox[0]), 0))

        indent_level_1, indent_level_2 = 90.0, 108.0
        if len(label_x0s) >= 5:
            from collections import Counter
            top_x0s = [x for x, _ in Counter(label_x0s).most_common(3)]
            top_x0s.sort()
            if len(top_x0s) >= 2:
                indent_level_1 = float(top_x0s[1]) if top_x0s[1] > top_x0s[0] + 2 else indent_level_1
            if len(top_x0s) >= 3:
                indent_level_2 = float(top_x0s[2]) if top_x0s[2] > indent_level_1 + 2 else indent_level_2

        return {
            "heading_after": round(section_gap * 0.75, 2),
            "row_height": round(row_height, 2),
            "section_gap": round(section_gap, 2),
            "subtotal_gap": round(row_height * 0.5, 2),
            "indent_level_1": round(indent_level_1, 2),
            "indent_level_2": round(indent_level_2, 2),
        }

    def _extract_font_roles(self, doc) -> Dict[str, Any]:
        """
        Role-based font mapping: classify each span by role rather than sorting by size.
        """
        import re
        from collections import Counter

        try:
            from core.document_format_analyzer import _AUDIT_SECTION_PATTERNS
        except ImportError:
            _AUDIT_SECTION_PATTERNS = []

        _NOTE_REF_RE = re.compile(r"^note\s*\d+$", re.IGNORECASE)
        _NUMERIC_ONLY_RE = re.compile(r"^[\d,.()\-–\s]+$")

        role_spans: Dict[str, List] = {
            "heading": [], "footer": [], "number": [], "note_ref": [], "body": [],
        }

        for page in doc:
            page_height = page.rect.height
            footer_y_threshold = page_height * 0.90

            blocks = page.get_text("dict", flags=0).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 9)
                        font = span.get("font", "Helvetica")
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        y0 = bbox[1]

                        if not text:
                            continue

                        if any(p.search(text) for p in _AUDIT_SECTION_PATTERNS):
                            role_spans["heading"].append((font, round(size, 1)))
                        elif size <= 8 and y0 >= footer_y_threshold:
                            role_spans["footer"].append((font, round(size, 1)))
                        elif _NOTE_REF_RE.match(text):
                            role_spans["note_ref"].append((font, round(size, 1)))
                        elif _NUMERIC_ONLY_RE.match(text) and len(text) >= 3:
                            role_spans["number"].append((font, round(size, 1)))
                        else:
                            role_spans["body"].append((font, round(size, 1)))

        def _most_common(spans) -> Dict[str, Any]:
            if not spans:
                return None
            (family, size), _ = Counter(spans).most_common(1)[0]
            return {"family": family, "size": size}

        fonts: Dict[str, Any] = {}
        for role in ("heading", "body", "footer", "number", "note_ref"):
            entry = _most_common(role_spans[role])
            if entry:
                fonts[role] = entry

        fonts.setdefault("heading", {"family": "Helvetica-Bold", "size": 12})
        fonts.setdefault("body", {"family": "Helvetica", "size": 9})
        fonts.setdefault("footer", {"family": "Helvetica", "size": 8})
        fonts.setdefault("number", fonts["body"])
        fonts.setdefault("note_ref", fonts["body"])

        return fonts
