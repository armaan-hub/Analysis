"""
Template Verifier: validates extracted template config against reference PDF.
Generates a verification report with confidence scores per check.
"""
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone


class TemplateVerifier:
    """
    Verifies a template config by comparing dimensions, margins, and fonts
    against known reference values.
    
    All verify_* methods return:
        {passed: bool, confidence: float, message: str, check: str}
    """

    def __init__(self, tolerance_pixels: float = 5.0):
        self.tolerance = tolerance_pixels

    def verify_page_dimensions(
        self,
        config: Dict[str, Any],
        reference_dims: Tuple[float, float],
    ) -> Dict[str, Any]:
        """Verify page dimensions match reference (width, height)."""
        page = config.get("page", {})
        cfg_w = page.get("width", 0)
        cfg_h = page.get("height", 0)
        ref_w, ref_h = reference_dims

        w_ok = abs(cfg_w - ref_w) <= self.tolerance
        h_ok = abs(cfg_h - ref_h) <= self.tolerance
        passed = w_ok and h_ok

        if not passed:
            msg = (
                f"Dimension mismatch: config ({cfg_w}×{cfg_h}) vs "
                f"reference ({ref_w}×{ref_h})"
            )
            confidence = 0.0
        else:
            msg = f"Page dimensions match ({cfg_w}×{cfg_h})"
            w_delta = abs(cfg_w - ref_w)
            h_delta = abs(cfg_h - ref_h)
            confidence = 1.0 - ((w_delta + h_delta) / (2 * self.tolerance * 2))
            confidence = round(max(0.0, min(1.0, confidence)), 3)

        return {"check": "page_dimensions", "passed": passed, "confidence": confidence, "message": msg}

    def verify_margins(
        self,
        config: Dict[str, Any],
        reference_margins: Dict[str, float],
    ) -> Dict[str, Any]:
        """Verify margins are within tolerance of reference."""
        cfg_margins = config.get("margins", {})
        checks = []
        for side in ("top", "bottom", "left", "right"):
            cfg_val = cfg_margins.get(side, 0)
            ref_val = reference_margins.get(side, 0)
            checks.append(abs(cfg_val - ref_val) <= self.tolerance)

        passed = all(checks)
        confidence = round(sum(checks) / len(checks), 3)
        msg = "Margins match reference" if passed else "Margin mismatch detected"
        return {"check": "margins", "passed": passed, "confidence": confidence, "message": msg}

    def verify_fonts(
        self,
        config: Dict[str, Any],
        expected_families: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Verify fonts section is populated and families are recognisable."""
        fonts = config.get("fonts", {})
        has_body = "body" in fonts and fonts["body"].get("size", 0) > 0
        has_heading = "heading" in fonts and fonts["heading"].get("size", 0) > 0

        passed = has_body and has_heading
        confidence = round((int(has_body) + int(has_heading)) / 2, 3)
        msg = "Font config OK" if passed else "Missing heading or body font configuration"

        if expected_families and passed:
            found = set()
            for v in fonts.values():
                found.add(v.get("family", "").lower())
            if not any(ef.lower() in found for ef in expected_families):
                passed = False
                confidence *= 0.5
                msg += f"; expected families {expected_families} not found in {list(found)}"

        return {"check": "fonts", "passed": passed, "confidence": confidence, "message": msg}

    def generate_report(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a full verification report from config.
        Runs all available checks and returns summary.
        """
        checks: List[Dict[str, Any]] = []

        # 1. Dimensions
        page = config.get("page", {})
        dims_result = self.verify_page_dimensions(
            config, (page.get("width", 0), page.get("height", 0))
        )
        checks.append(dims_result)

        # 2. Margins
        margins = config.get("margins", {})
        margins_result = self.verify_margins(config, margins)
        checks.append(margins_result)

        # 3. Fonts
        fonts_result = self.verify_fonts(config)
        checks.append(fonts_result)

        # 4. Sections present
        sections = config.get("sections", [])
        sections_ok = len(sections) > 0
        checks.append({
            "check": "sections",
            "passed": sections_ok,
            "confidence": 1.0 if sections_ok else 0.0,
            "message": f"{len(sections)} section(s) detected" if sections_ok else "No sections detected",
        })

        passed_count = sum(1 for c in checks if c["passed"])
        overall_passed = passed_count == len(checks)
        overall_confidence = round(sum(c["confidence"] for c in checks) / len(checks), 3)

        return {
            "overall_passed": overall_passed,
            "confidence": overall_confidence,
            "checks": checks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": f"{passed_count}/{len(checks)} checks passed",
        }
