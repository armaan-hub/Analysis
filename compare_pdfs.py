import fitz
import os

# Paths
generated = r"Testing data\Castle_Plaza_Audit_2025_v3.pdf"
reference = r"Testing data\Draft FS - Castle Plaza 2025.pdf"

print("="*80)
print("GENERATED PDF ANALYSIS")
print("="*80)
try:
    doc_gen = fitz.open(generated)
    print(f"📄 File: {os.path.basename(generated)}")
    print(f"📊 Total Pages: {len(doc_gen)}")
    print(f"📏 Page Size (first page): {doc_gen[0].rect}")
    
    # Check for 2024 data in SOFP (usually page 3)
    if len(doc_gen) >= 3:
        sofp_text = doc_gen[2].get_text()
        print(f"\n--- PAGE 3 (SOFP) - First 1000 chars ---")
        print(sofp_text[:1000])
        if "2024" in sofp_text or "Prior" in sofp_text:
            print("✓ Contains 2024/Prior year data")
        else:
            print("✗ NO 2024/Prior year data visible")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*80)
print("REFERENCE PDF ANALYSIS")
print("="*80)
try:
    doc_ref = fitz.open(reference)
    print(f"📄 File: {os.path.basename(reference)}")
    print(f"📊 Total Pages: {len(doc_ref)}")
    print(f"📏 Page Size (first page): {doc_ref[0].rect}")
    
    # Check for 2024 data
    for i in range(min(5, len(doc_ref))):
        text = doc_ref[i].get_text()
        if "STATEMENT" in text.upper() and ("FINANCIAL" in text.upper() or "POSITION" in text.upper()):
            print(f"\n--- PAGE {i+1} (SOFP) - First 1000 chars ---")
            print(text[:1000])
            if "2024" in text or "Prior" in text:
                print("✓ Contains 2024/Prior year data")
            break
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*80)
print("KEY OBSERVATIONS - FORMAT GAPS")
print("="*80)
print("""
LIKELY DIFFERENCES:
1. ❌ MISSING 2024 COMPARATIVE DATA
   - Generated PDF: Shows '-' or empty for 2024 columns
   - Reference PDF: Shows actual 2024 figures
   - Root cause: prior_year_extractor output NOT wired into report

2. ❓ POSSIBLE LAYOUT DIFFERENCES
   - Column widths
   - Font sizes/weights
   - Row spacing/padding
   - Note alignment
   - Page header/footer formatting

3. ❓ POSSIBLE CONTENT STRUCTURE
   - Note numbering alignment
   - Table grouping/hierarchy
   - Currency symbols placement
   - Section breaks/spacing
""")
