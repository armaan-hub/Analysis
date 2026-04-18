"""
Pre-built format library shipped with the app.
Provides ready-to-use IFRS, GAAP, and Local Tax templates without requiring
a reference PDF upload.
"""
from typing import Optional

PREBUILT_FORMATS = [
    {
        "id": "prebuilt-ifrs-standard",
        "name": "IFRS Standard",
        "format_family": "IFRS",
        "format_variant": "IFRS 2023",
        "description": "Standard IFRS financial statement format",
        "config": {
            "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
            "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [
                {"name": "cover", "page": 1, "layout": "static"},
                {"name": "sofp", "page": 2, "layout": "flow"},
                {"name": "sopl", "page": 3, "layout": "flow"},
                {"name": "notes", "pages": [4, 5, 6, 7, 8], "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {
                    "page_size": 1.0,
                    "margins": 1.0,
                    "fonts": 0.9,
                    "tables": 0.8,
                },
            },
        },
        "fingerprint": {
            "page_size": "A4",
            "currency": "USD",
            "section_count": 4,
            "has_notes": True,
            "col_count": 2,
            "format_family": "IFRS",
        },
    },
    {
        "id": "prebuilt-gaap-standard",
        "name": "GAAP Standard",
        "format_family": "GAAP",
        "format_variant": "US GAAP",
        "description": "Standard US GAAP financial statement format",
        "config": {
            "page": {"width": 612, "height": 792, "unit": "points", "detected_size": "US_LETTER", "confidence": 1.0},
            "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 10},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [
                {"name": "cover", "page": 1, "layout": "static"},
                {"name": "balance_sheet", "page": 2, "layout": "flow"},
                {"name": "income_statement", "page": 3, "layout": "flow"},
                {"name": "cash_flow", "page": 4, "layout": "flow"},
                {"name": "notes", "pages": [5, 6, 7, 8], "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {
                    "page_size": 1.0,
                    "margins": 1.0,
                    "fonts": 0.9,
                    "tables": 0.8,
                },
            },
        },
        "fingerprint": {
            "page_size": "US_LETTER",
            "currency": "USD",
            "section_count": 5,
            "has_notes": True,
            "col_count": 2,
            "format_family": "GAAP",
        },
    },
    {
        "id": "prebuilt-local-tax",
        "name": "Local Tax Return",
        "format_family": "local-tax",
        "format_variant": "UAE Corporate Tax 2024",
        "description": "UAE Corporate Tax return format",
        "config": {
            "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
            "margins": {"top": 56, "bottom": 56, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 11},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 7},
            },
            "tables": [],
            "sections": [
                {"name": "tax_period", "page": 1, "layout": "static"},
                {"name": "revenue", "page": 2, "layout": "flow"},
                {"name": "deductions", "page": 3, "layout": "flow"},
                {"name": "tax_computation", "page": 4, "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {
                    "page_size": 1.0,
                    "margins": 1.0,
                    "fonts": 0.9,
                    "tables": 0.8,
                },
            },
        },
        "fingerprint": {
            "page_size": "A4",
            "currency": "AED",
            "section_count": 4,
            "has_notes": False,
            "col_count": 2,
            "format_family": "local-tax",
        },
    },
    {
        "id": "prebuilt-uk-frs102",
        "name": "UK FRS 102",
        "format_family": "IFRS",
        "format_variant": "UK FRS 102",
        "description": "UK Financial Reporting Standard for medium-sized entities",
        "config": {
            "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
            "margins": {"top": 56, "bottom": 56, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 11},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [
                {"name": "cover", "page": 1, "layout": "static"},
                {"name": "directors_report", "page": 2, "layout": "flow"},
                {"name": "balance_sheet", "page": 3, "layout": "flow"},
                {"name": "profit_loss", "page": 4, "layout": "flow"},
                {"name": "notes", "pages": [5, 6, 7, 8, 9], "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {"page_size": 1.0, "margins": 1.0, "fonts": 0.9, "tables": 0.8},
            },
        },
        "fingerprint": {
            "page_size": "A4",
            "currency": "GBP",
            "section_count": 5,
            "has_notes": True,
            "col_count": 2,
            "format_family": "IFRS",
        },
    },
    {
        "id": "prebuilt-saudi-zatca",
        "name": "Saudi ZATCA",
        "format_family": "local-tax",
        "format_variant": "Saudi ZATCA 2024",
        "description": "Saudi Arabia Zakat, Tax and Customs Authority financial reporting format",
        "config": {
            "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
            "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [
                {"name": "cover", "page": 1, "layout": "static"},
                {"name": "zakat_computation", "page": 2, "layout": "flow"},
                {"name": "financial_position", "page": 3, "layout": "flow"},
                {"name": "income_statement", "page": 4, "layout": "flow"},
                {"name": "notes", "pages": [5, 6, 7, 8], "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {"page_size": 1.0, "margins": 1.0, "fonts": 0.9, "tables": 0.8},
            },
        },
        "fingerprint": {
            "page_size": "A4",
            "currency": "SAR",
            "section_count": 5,
            "has_notes": True,
            "col_count": 2,
            "format_family": "local-tax",
        },
    },
    {
        "id": "prebuilt-gcc-standard",
        "name": "GCC Standard",
        "format_family": "IFRS",
        "format_variant": "GCC IFRS",
        "description": "Gulf Cooperation Council standard financial statement format (IAS-compliant)",
        "config": {
            "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
            "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
            "fonts": {
                "heading": {"family": "Helvetica-Bold", "size": 12},
                "body": {"family": "Helvetica", "size": 9},
                "footer": {"family": "Helvetica", "size": 8},
            },
            "tables": [],
            "sections": [
                {"name": "cover", "page": 1, "layout": "static"},
                {"name": "sofp", "page": 2, "layout": "flow"},
                {"name": "sopl", "page": 3, "layout": "flow"},
                {"name": "soce", "page": 4, "layout": "flow"},
                {"name": "cfs", "page": 5, "layout": "flow"},
                {"name": "notes", "pages": [6, 7, 8, 9, 10], "layout": "flow"},
            ],
            "substitutions": {},
            "extraction_metadata": {
                "analyzer_version": "prebuilt",
                "source": "prebuilt",
                "confidence_per_element": {"page_size": 1.0, "margins": 1.0, "fonts": 0.9, "tables": 0.8},
            },
        },
        "fingerprint": {
            "page_size": "A4",
            "page_size_alts": ["US_LETTER"],
            "currency": "AED",
            "section_count": 6,
            "has_notes": True,
            "col_count": 3,
            "format_family": "IFRS",
        },
    },
]


def get_prebuilt_by_id(format_id: str) -> Optional[dict]:
    """Return prebuilt format dict by id, or None."""
    return next((f for f in PREBUILT_FORMATS if f["id"] == format_id), None)


def get_prebuilt_by_family(format_family: str) -> list:
    """Return all prebuilt formats for a format_family."""
    return [f for f in PREBUILT_FORMATS if f["format_family"] == format_family]
