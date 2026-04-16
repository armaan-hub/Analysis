import fitz
import json
from pathlib import Path

# Extract detailed PDF structure
generated = r"Testing data\Castle_Plaza_Audit_2025_v3.pdf"
reference = r"Testing data\Draft FS - Castle Plaza 2025.pdf"

def analyze_pdf_detailed(path, label):
    print(f"\n{'='*100}")
    print(f"  {label}")
    print(f"{'='*100}\n")
    
    doc = fitz.open(path)
    print(f"📊 METADATA:")
    print(f"   Total Pages: {len(doc)}")
    print(f"   Page Size: {doc[0].rect}")
    print(f"   File Size: {Path(path).stat().st_size / 1024:.1f} KB")
    
    # Page-by-page analysis
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # Detect what page this is
        page_type = "UNKNOWN"
        if "INDEPENDENT AUDITOR'S REPORT" in text:
            page_type = "AUDITOR'S REPORT"
        elif "STATEMENT OF FINANCIAL POSITION" in text:
            page_type = "STATEMENT OF FINANCIAL POSITION"
        elif "STATEMENT OF PROFIT OR LOSS" in text or "STATEMENT OF COMPREHENSIVE INCOME" in text:
            page_type = "STATEMENT OF PROFIT/LOSS"
        elif "STATEMENT OF CHANGES" in text:
            page_type = "STATEMENT OF CHANGES"
        elif "CASH FLOWS" in text:
            page_type = "STATEMENT OF CASH FLOWS"
        elif "NOTES" in text.upper():
            page_type = "NOTES"
        
        has_2024 = "2024" in text
        has_2025 = "2025" in text
        has_notes = "Note " in text
        has_tables = "AED" in text or "Currency" in text
        
        print(f"\n📄 PAGE {page_num + 1:2d} | {page_type:30s} | Text: {len(text):5d} chars", end="")
        if has_2024:
            print(" | ✓ 2024", end="")
        if has_2025:
            print(" | ✓ 2025", end="")
        if has_tables:
            print(" | ✓ TABLES", end="")
        if has_notes:
            print(" | ✓ NOTES", end="")
        print()

print("\n" + "█"*100)
print("█" + " "*98 + "█")
print("█" + "  DETAILED PDF STRUCTURE COMPARISON".center(98) + "█")
print("█" + " "*98 + "█")
print("█"*100)

analyze_pdf_detailed(generated, "GENERATED PDF (Castle_Plaza_Audit_2025_v3.pdf)")
analyze_pdf_detailed(reference, "REFERENCE PDF (Draft FS - Castle Plaza 2025.pdf)")

print("\n" + "█"*100)
print("█" + " "*98 + "█")
print("█" + "  CONTENT SAMPLE - PAGE BY PAGE".center(98) + "█")
print("█" + " "*98 + "█")
print("█"*100)

doc_gen = fitz.open(generated)
doc_ref = fitz.open(reference)

print("\n\n" + "="*100)
print("GENERATED PDF - KEY PAGES")
print("="*100)

# Find and display SOFP page
for i, page in enumerate(doc_gen):
    text = page.get_text()
    if "STATEMENT OF FINANCIAL POSITION" in text:
        print(f"\n[PAGE {i+1}] STATEMENT OF FINANCIAL POSITION")
        print("─"*100)
        lines = text.split('\n')
        for j, line in enumerate(lines[:50]):  # First 50 lines
            if line.strip():
                print(f"{line[:100]}")
        break

print("\n\n" + "="*100)
print("REFERENCE PDF - KEY PAGES")
print("="*100)

# Find and display SOFP page
for i, page in enumerate(doc_ref):
    text = page.get_text()
    if "STATEMENT OF FINANCIAL POSITION" in text:
        print(f"\n[PAGE {i+1}] STATEMENT OF FINANCIAL POSITION")
        print("─"*100)
        lines = text.split('\n')
        for j, line in enumerate(lines[:50]):  # First 50 lines
            if line.strip():
                print(f"{line[:100]}")
        break

print("\n\n" + "="*100)
print("QUICK COMPARISON SUMMARY")
print("="*100)
print(f"Generated PDF: {len(doc_gen)} pages")
print(f"Reference PDF: {len(doc_ref)} pages")
print(f"Page Difference: {len(doc_ref) - len(doc_gen)} pages")
