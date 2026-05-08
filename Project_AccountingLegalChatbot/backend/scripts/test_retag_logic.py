"""
Test script to verify the logic of retag_vector_store.py using a mock collection.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add backend to sys.path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.domains import infer_domain_from_name

def test_logic():
    print("Testing infer_domain_from_name logic...")
    
    test_cases = [
        ("17. Free Zone Persons 20052024.pdf", "corporate_tax"),
        ("VAT Treatment on Sale of Goods from UAE Free Zone to Mainland..pdf", "vat"),
        ("Purchase of Commercial Property - General.docx", "commercial"),
        ("20. Charities.pdf", "corporate_tax"),
        ("random_doc.pdf", "general"),
    ]
    
    for name, expected in test_cases:
        actual = infer_domain_from_name(name)
        status = "PASS" if actual == expected else "FAIL"
        print(f"  {name:60} -> {actual:15} ({status}, expected {expected})")
        if actual != expected:
            print(f"    ERROR: expected {expected}, got {actual}")

if __name__ == "__main__":
    test_logic()
