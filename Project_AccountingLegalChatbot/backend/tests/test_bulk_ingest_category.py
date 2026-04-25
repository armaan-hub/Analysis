from pathlib import Path

def test_bulk_ingest_passes_category_to_ingest_chunks():
    """bulk_ingest.py must pass category= and original_name= to ingest_chunks().
    
    Without this, all pre-loaded UAE law/finance documents get category='general'
    in ChromaDB and become completely invisible to category-filtered searches.
    """
    source = Path("bulk_ingest.py").read_text(encoding="utf-8")
    assert "category=category" in source, (
        "bulk_ingest.py must pass category=category to ingest_chunks(). "
        "Without this, all pre-loaded documents get category='general' and become unsearchable."
    )
    assert "original_name=name" in source or "original_name=file_path.name" in source, (
        "bulk_ingest.py must pass original_name= to ingest_chunks() for readable source names."
    )
