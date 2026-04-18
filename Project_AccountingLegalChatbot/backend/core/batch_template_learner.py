"""
Batch Template Learner: analyze multiple reference PDFs and produce a
consensus template config with higher confidence.
"""
from typing import List, Dict, Any
from core.template_analyzer import TemplateAnalyzer


class BatchTemplateLearner:
    """
    Analyzes multiple PDFs of the same audit format and produces a
    consensus template config by averaging/voting across samples.
    Higher confidence than single-PDF extraction.
    """

    def __init__(self):
        self.analyzer = TemplateAnalyzer()

    def learn_from_multiple(self, pdf_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze multiple PDFs and return a consensus config.

        Args:
            pdf_paths: List of paths to reference PDFs (same format)

        Returns:
            Consensus template config dict with boosted confidence
        """
        if not pdf_paths:
            raise ValueError("At least one PDF path is required")

        configs = []
        errors = []
        for path in pdf_paths:
            config = self.analyzer.analyze(path)
            if config.get("confidence", 0) > 0:
                configs.append(config)
            else:
                errors.append({"path": path, "error": config.get("error", "Unknown")})

        if not configs:
            raise ValueError(f"Could not extract config from any PDF. Errors: {errors}")

        consensus = self._merge_configs(configs)
        consensus["batch_metadata"] = {
            "pdf_count": len(pdf_paths),
            "successful_extractions": len(configs),
            "failed_extractions": len(errors),
            "errors": errors,
        }
        return consensus

    def _merge_configs(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple configs by averaging numeric values and voting on strings."""
        # Page dimensions: average
        page_widths = [c["page"]["width"] for c in configs if c.get("page", {}).get("width")]
        page_heights = [c["page"]["height"] for c in configs if c.get("page", {}).get("height")]

        page = {
            "width": round(sum(page_widths) / len(page_widths), 2) if page_widths else 612,
            "height": round(sum(page_heights) / len(page_heights), 2) if page_heights else 792,
            "unit": "points",
        }

        # Margins: average
        margin_keys = ["top", "bottom", "left", "right"]
        margins = {}
        for key in margin_keys:
            vals = [c.get("margins", {}).get(key) for c in configs if c.get("margins", {}).get(key) is not None]
            margins[key] = round(sum(vals) / len(vals), 2) if vals else 72.0

        # Fonts: average sizes, vote on families
        fonts = {}
        for role in ("heading", "body", "footer"):
            sizes = [c.get("fonts", {}).get(role, {}).get("size") for c in configs]
            sizes = [s for s in sizes if s is not None]
            families = [c.get("fonts", {}).get(role, {}).get("family") for c in configs]
            families = [f for f in families if f]
            # majority vote on family
            family = max(set(families), key=families.count) if families else "Helvetica"
            size = round(sum(sizes) / len(sizes), 1) if sizes else (12 if role == "heading" else 9)
            fonts[role] = {"family": family, "size": size}

        # Sections: union from all configs
        seen_names = set()
        sections = []
        for c in configs:
            for s in c.get("sections", []):
                name = s.get("name", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    sections.append(s)

        # Confidence: boosted by number of agreeing samples
        base_confidence = sum(c.get("confidence", 0) for c in configs) / len(configs)
        boost = min(0.15 * (len(configs) - 1), 0.25)  # up to +0.25 for 3+ samples
        consensus_confidence = min(round(base_confidence + boost, 2), 1.0)

        # Page count: max across all (most comprehensive)
        page_counts = [c.get("page_count", 0) for c in configs]
        page_count = max(page_counts) if page_counts else 0

        # Source names
        sources = [c.get("source", "") for c in configs if c.get("source")]

        return {
            "page": page,
            "margins": margins,
            "fonts": fonts,
            "tables": [],
            "sections": sections,
            "confidence": consensus_confidence,
            "source": ", ".join(sources),
            "page_count": page_count,
        }
