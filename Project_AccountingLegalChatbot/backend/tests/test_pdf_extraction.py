import pytest
from db.models import Document


def test_document_model_has_new_rag_fields():
    """Document model must carry pipeline fields before we can test anything else."""
    required = {
        "source_dir", "domain", "jurisdiction", "law_number",
        "subjects", "effective_date", "is_arabic", "was_translated", "indexed_at",
    }
    cols = {c.key for c in Document.__table__.columns}
    missing = required - cols
    assert not missing, f"Document model missing columns: {missing}"
