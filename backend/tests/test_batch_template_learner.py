"""Tests for BatchTemplateLearner."""
import pytest
from core.batch_template_learner import BatchTemplateLearner


def _make_config(
    family="Helvetica",
    h_size=12.0,
    b_size=9.0,
    f_size=8.0,
    margins=None,
    confidence=0.8,
    source="a.pdf",
    page_count=5,
    width=612,
    height=792,
    sections=None,
):
    if margins is None:
        margins = {"top": 72, "bottom": 72, "left": 72, "right": 72}
    if sections is None:
        sections = []
    return {
        "page": {"width": width, "height": height, "unit": "points"},
        "margins": margins,
        "fonts": {
            "heading": {"family": family, "size": h_size},
            "body": {"family": family, "size": b_size},
            "footer": {"family": family, "size": f_size},
        },
        "sections": sections,
        "confidence": confidence,
        "source": source,
        "page_count": page_count,
    }


def test_learn_from_single_nonexistent_pdf_raises():
    """learn_from_multiple with a nonexistent PDF should raise ValueError."""
    learner = BatchTemplateLearner()
    with pytest.raises(ValueError, match="Could not extract config"):
        learner.learn_from_multiple(["nonexistent.pdf"])


def test_learn_from_all_failing_pdfs_raises():
    """All-failing PDFs should raise ValueError."""
    learner = BatchTemplateLearner()
    with pytest.raises(ValueError, match="Could not extract config"):
        learner.learn_from_multiple(["nonexistent_1.pdf", "nonexistent_2.pdf"])


def test_learn_from_zero_pdfs_raises():
    learner = BatchTemplateLearner()
    with pytest.raises(ValueError, match="At least one PDF path is required"):
        learner.learn_from_multiple([])


def test_merge_configs_averages_margins():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(margins={"top": 70, "bottom": 70, "left": 70, "right": 70},
                     confidence=0.8, source="a.pdf", page_count=5,
                     width=612, height=792),
        _make_config(margins={"top": 74, "bottom": 74, "left": 74, "right": 74},
                     confidence=0.7, source="b.pdf", page_count=6,
                     width=614, height=794),
    ]
    result = learner._merge_configs(configs)
    assert result["margins"]["top"] == 72.0
    assert result["margins"]["bottom"] == 72.0
    assert result["page"]["width"] == 613.0
    assert result["confidence"] > 0.7  # boosted


def test_merge_configs_averages_page_dimensions():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(width=610, height=790),
        _make_config(width=614, height=794),
    ]
    result = learner._merge_configs(configs)
    assert result["page"]["width"] == 612.0
    assert result["page"]["height"] == 792.0


def test_merge_fonts_majority_vote():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(family="Times", h_size=14, b_size=10, source="a.pdf", confidence=0.8),
        _make_config(family="Times", h_size=13, b_size=9, source="b.pdf", confidence=0.7),
        _make_config(family="Helvetica", h_size=12, b_size=9, source="c.pdf", confidence=0.6),
    ]
    result = learner._merge_configs(configs)
    assert result["fonts"]["heading"]["family"] == "Times"  # majority (2 vs 1)
    assert result["fonts"]["body"]["family"] == "Times"


def test_merge_fonts_averages_sizes():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(h_size=14.0, source="a.pdf"),
        _make_config(h_size=12.0, source="b.pdf"),
    ]
    result = learner._merge_configs(configs)
    assert result["fonts"]["heading"]["size"] == 13.0


def test_confidence_boost_with_multiple_pdfs():
    learner = BatchTemplateLearner()
    single_config = _make_config(confidence=0.7, source="a.pdf")
    result_single = learner._merge_configs([single_config])
    result_multi = learner._merge_configs([single_config, single_config, single_config])
    assert result_multi["confidence"] > result_single["confidence"]


def test_confidence_capped_at_one():
    learner = BatchTemplateLearner()
    # Very high confidence + max boost should never exceed 1.0
    configs = [_make_config(confidence=0.95, source=f"{i}.pdf") for i in range(5)]
    result = learner._merge_configs(configs)
    assert result["confidence"] <= 1.0


def test_single_config_no_boost():
    learner = BatchTemplateLearner()
    result = learner._merge_configs([_make_config(confidence=0.8)])
    # boost = 0.15 * (1 - 1) = 0.0
    assert result["confidence"] == 0.8


def test_sections_union_deduplication():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(sections=[{"name": "cover", "page": 1}, {"name": "notes", "page": 3}]),
        _make_config(sections=[{"name": "cover", "page": 1}, {"name": "financials", "page": 2}]),
    ]
    result = learner._merge_configs(configs)
    section_names = [s["name"] for s in result["sections"]]
    # "cover" should appear only once
    assert section_names.count("cover") == 1
    assert "notes" in section_names
    assert "financials" in section_names


def test_page_count_is_max():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(page_count=5),
        _make_config(page_count=10),
        _make_config(page_count=7),
    ]
    result = learner._merge_configs(configs)
    assert result["page_count"] == 10


def test_source_combines_filenames():
    learner = BatchTemplateLearner()
    configs = [
        _make_config(source="a.pdf"),
        _make_config(source="b.pdf"),
    ]
    result = learner._merge_configs(configs)
    assert "a.pdf" in result["source"]
    assert "b.pdf" in result["source"]


def test_batch_metadata_included_in_learn_from_multiple(monkeypatch):
    """learn_from_multiple adds batch_metadata to result."""
    learner = BatchTemplateLearner()
    # Monkeypatch analyzer to return a valid config without needing real PDFs
    monkeypatch.setattr(
        learner.analyzer,
        "analyze",
        lambda path: _make_config(confidence=0.85, source=path),
    )
    result = learner.learn_from_multiple(["fake1.pdf", "fake2.pdf"])
    assert "batch_metadata" in result
    assert result["batch_metadata"]["pdf_count"] == 2
    assert result["batch_metadata"]["successful_extractions"] == 2
    assert result["batch_metadata"]["failed_extractions"] == 0
