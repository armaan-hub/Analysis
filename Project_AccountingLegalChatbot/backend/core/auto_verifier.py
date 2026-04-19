"""
AutoVerifier — Phase 3 of the fast format learning pipeline.

Renders a test page using extracted config (ReportLab), pixel-diffs against
the reference PDF page 1 (Pillow/NumPy), then auto-approves, applies one
adjustment pass, or returns StructuredHints for the user.
"""
from __future__ import annotations

import copy
import io
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image


class AutoVerifier:
    """Verify extracted template config via pixel comparison."""

    PASS_THRESHOLD = 0.95
    ADJUST_THRESHOLD = 0.85
    RENDER_DPI = 150

    def verify(self, config: Dict[str, Any], pdf_path: str) -> Dict[str, Any]:
        """
        Run the full verification cycle.

        Returns:
            {
              "status":     "verified" | "needs_review",
              "confidence": float,
              "hints":      list | None,
              "adjusted":   bool,
            }
        """
        try:
            ref_image = self._pdf_page_to_image(pdf_path)
        except Exception:
            return {"status": "needs_review", "confidence": 0.75, "hints": None, "adjusted": False}

        try:
            test_pdf_bytes = self._render_test_page(config)
            test_image = self._pdf_bytes_to_image(test_pdf_bytes)
        except Exception:
            return {"status": "needs_review", "confidence": 0.75, "hints": None, "adjusted": False}

        score = self.pixel_similarity(ref_image, test_image)

        if score >= self.PASS_THRESHOLD:
            return {"status": "verified", "confidence": round(score, 4), "hints": None, "adjusted": False}

        if score >= self.ADJUST_THRESHOLD:
            adj_config = self._auto_adjust(config, ref_image, test_image)
            try:
                adj_bytes = self._render_test_page(adj_config)
                adj_image = self._pdf_bytes_to_image(adj_bytes)
                adj_score = self.pixel_similarity(ref_image, adj_image)
            except Exception:
                adj_score = score

            if adj_score >= self.PASS_THRESHOLD:
                return {"status": "verified", "confidence": round(adj_score, 4), "hints": None, "adjusted": True}

        hints = self._generate_hints(config, ref_image, test_image, score)
        return {"status": "needs_review", "confidence": round(score, 4), "hints": hints, "adjusted": False}

    @staticmethod
    def pixel_similarity(img_ref: Image.Image, img_test: Image.Image) -> float:
        """
        Compute pixel similarity between two grayscale images.
        Returns 1.0 for identical, 0.0 for maximum difference.
        """
        img_test = img_test.resize(img_ref.size, Image.Resampling.LANCZOS)
        arr_ref = np.array(img_ref.convert("L"), dtype=float)
        arr_test = np.array(img_test.convert("L"), dtype=float)
        diff = np.abs(arr_ref - arr_test).mean()
        return round(1.0 - (diff / 255.0), 4)

    def _pdf_page_to_image(self, pdf_path: str, page_num: int = 0) -> Image.Image:
        import fitz
        doc = None
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            mat = fitz.Matrix(self.RENDER_DPI / 72, self.RENDER_DPI / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            return Image.frombytes("L", [pix.width, pix.height], pix.samples)
        finally:
            if doc:
                doc.close()

    def _pdf_bytes_to_image(self, pdf_bytes: bytes, page_num: int = 0) -> Image.Image:
        import fitz
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[page_num]
            mat = fitz.Matrix(self.RENDER_DPI / 72, self.RENDER_DPI / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            return Image.frombytes("L", [pix.width, pix.height], pix.samples)
        finally:
            if doc:
                doc.close()

    def _render_test_page(self, config: Dict[str, Any]) -> bytes:
        """Render a representative financial page using the extracted config."""
        from reportlab.pdfgen import canvas as rl_canvas

        page = config.get("page", {})
        w = float(page.get("width", 595.28))
        h = float(page.get("height", 841.89))

        margins = config.get("margins", {})
        columns = config.get("columns", {})
        spacing = config.get("spacing", {})
        fonts = config.get("fonts", {})

        body_font = fonts.get("body", {}).get("family", "Helvetica")
        body_size = float(fonts.get("body", {}).get("size", 9))
        heading_font = fonts.get("heading", {}).get("family", "Helvetica-Bold")
        heading_size = float(fonts.get("heading", {}).get("size", 12))

        left = float(margins.get("left", 72))
        top_margin = float(margins.get("top", 72))
        row_h = float(spacing.get("row_height", 14))
        heading_after = float(spacing.get("heading_after", 18))

        year1_x = float(columns.get("year1_col_x", w * 0.65))
        year2_x = float(columns.get("year2_col_x", w * 0.80))

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w, h))

        curr_y = h - top_margin

        c.setFont(heading_font, heading_size)
        c.drawString(left, curr_y, "STATEMENT OF FINANCIAL POSITION")
        curr_y -= heading_after

        c.setFont(body_font, body_size)
        c.drawRightString(year1_x + 30, curr_y, "2024")
        c.drawRightString(year2_x + 30, curr_y, "2023")
        curr_y -= row_h

        line_items = [
            ("Non-current assets", 12_450_000, 11_200_000),
            ("Property and equipment", 8_320_000, 7_900_000),
            ("Intangible assets", 1_200_000, 1_100_000),
            ("Current assets", 5_430_000, 4_800_000),
            ("Trade receivables", 2_100_000, 1_950_000),
            ("Cash and bank", 3_330_000, 2_850_000),
            ("Total assets", 17_880_000, 16_000_000),
        ]
        for label, val1, val2 in line_items:
            c.drawString(left, curr_y, label)
            c.drawRightString(year1_x + 30, curr_y, f"{val1:,}")
            c.drawRightString(year2_x + 30, curr_y, f"{val2:,}")
            curr_y -= row_h
            if curr_y < 72:
                break

        c.save()
        return buf.getvalue()

    def _auto_adjust(
        self,
        config: Dict[str, Any],
        ref_image: Image.Image,
        test_image: Image.Image,
    ) -> Dict[str, Any]:
        """Single-pass auto-adjustment based on worst band analysis."""
        adj = copy.deepcopy(config)
        h = ref_image.height
        band_size = max(h // 6, 1)

        ref_arr = np.array(ref_image.convert("L"), dtype=float)
        test_arr = np.array(test_image.resize(ref_image.size, Image.Resampling.LANCZOS).convert("L"), dtype=float)

        band_diffs = []
        for i in range(6):
            y0 = i * band_size
            y1 = (i + 1) * band_size if i < 5 else h
            diff = float(np.abs(ref_arr[y0:y1] - test_arr[y0:y1]).mean())
            band_diffs.append((diff, i))

        _, worst_band = max(band_diffs)

        adj.setdefault("margins", {})
        adj.setdefault("columns", {})
        adj.setdefault("spacing", {})

        if worst_band == 0:
            adj["margins"]["top"] = adj["margins"].get("top", 72) + 4
        elif worst_band in (2, 3):
            adj["columns"]["year1_col_x"] = adj["columns"].get("year1_col_x", 380.0) + 3
        else:
            adj["spacing"]["row_height"] = adj["spacing"].get("row_height", 14.0) + 1

        return adj

    def _generate_hints(
        self,
        config: Dict[str, Any],
        ref_image: Image.Image,
        test_image: Image.Image,
        score: float,
    ) -> List[Dict[str, Any]]:
        """Generate StructuredHints — targeted binary choices for the user."""
        h = ref_image.height
        band_size = max(h // 6, 1)

        ref_arr = np.array(ref_image.convert("L"), dtype=float)
        test_arr = np.array(test_image.resize(ref_image.size, Image.Resampling.LANCZOS).convert("L"), dtype=float)

        hints: List[Dict[str, Any]] = []
        for i in range(6):
            y0 = i * band_size
            y1 = (i + 1) * band_size if i < 5 else h
            band_diff = float(np.abs(ref_arr[y0:y1] - test_arr[y0:y1]).mean())

            if band_diff < 30:
                continue

            if i == 0:
                nudge = max(1, round(band_diff / 10))
                hints.append({
                    "element": "margins",
                    "message": f"Top margin appears to be off by approximately {nudge}pt",
                    "options": [f"adjust top margin by +{nudge}pt", "leave as-is"],
                })
            elif i in (1, 2):
                nudge = max(1, round(band_diff / 5) * 3)
                hints.append({
                    "element": "columns",
                    "message": f"Column position appears {nudge}pt off",
                    "options": [f"shift left {nudge}pt", "leave as-is"],
                })
            else:
                nudge = max(1, round(band_diff / 20))
                hints.append({
                    "element": "spacing.row_height",
                    "message": f"Row height appears {nudge}pt smaller than reference",
                    "options": [f"increase by {nudge}pt", "leave as-is"],
                })

        if not hints:
            hints.append({
                "element": "layout",
                "message": "Layout could not be verified automatically. Manual review required.",
                "options": ["approve manually", "discard template"],
            })

        return hints
