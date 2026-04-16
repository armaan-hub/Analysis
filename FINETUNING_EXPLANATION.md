# FINE-TUNING EXPLANATION
## What Tools & Languages Are We Using?

---

## QUICK ANSWER

**We're using PYTHON, NOT LLM.**

- 🐍 **Python** → For PDF generation (ReportLab library)
- ❌ **NOT LLM** → LLM can't directly adjust PDF formatting
- ❌ **NOT Manual** → We're not editing PDFs by hand
- ✅ **Programmatic** → Changing Python code parameters → regenerate PDF

---

## HOW IT WORKS

### Current System Architecture

```
User uploads documents
  ↓
LLM extracts financial data (2024, 2025, notes, etc.)
  ↓
Python converts extracted data to structured JSON
  ↓
ReportLab (Python library) generates PDF from JSON
  ↓
User downloads generated PDF
```

### Where Fine-Tuning Happens

```
format_applier.py (Python code)
├─ pagesize = (612, 792)  ← FINE-TUNING PARAMETER #1
├─ margins = (50, 50)     ← FINE-TUNING PARAMETER #2
├─ column_width = 170     ← FINE-TUNING PARAMETER #3
├─ font_size = 10         ← FINE-TUNING PARAMETER #4
├─ spacing = 12           ← FINE-TUNING PARAMETER #5
├─ padding = 8            ← FINE-TUNING PARAMETER #6
└─ ... (20+ more parameters)

When we change these parameters:
  → Python regenerates PDF
  → We compare new PDF to reference
  → If closer, keep change
  → If not, adjust differently
```

---

## CONCRETE EXAMPLE: Changing Page Size

### Step 1: Identify the Parameter in Code

**File**: `backend/core/format_applier.py` (line ~386)

```python
# CURRENT (WRONG):
pagesize = pagesize.A4  # 595 × 841.89 points
```

### Step 2: Change the Parameter

```python
# CHANGE TO (CORRECT):
pagesize = (612, 792)   # US Letter size
```

### Step 3: Regenerate PDF

```bash
python -m pytest tests/test_pdf_generation.py
# OR
python generate_pdf.py
```

### Step 4: Compare New PDF to Reference

```
Generated PDF (NEW):
  Page size: 612 × 792 ✓ MATCHES
  Column widths: Now 170 instead of 165 ✓ BETTER
  Page breaks: Fewer pages ✓ CLOSER to reference
```

### Step 5: Iterate

If still not perfect:
```python
# Maybe fonts are still wrong size
font_size = 11  # Changed from 10

# Regenerate → Compare → Iterate
```

---

## PARAMETERS WE'LL FINE-TUNE

All changed in **Python code only**, no LLM involved:

### **Format Parameters** (in `format_applier.py`)
```python
# Page dimensions
pagesize = (612, 792)              # Width × Height (US Letter)

# Margins
left_margin = 50
right_margin = 50
top_margin = 50
bottom_margin = 50

# Table columns
sofp_col_name_width = 200          # Account name column width
sofp_col_2025_width = 160          # 2025 amount column width
sofp_col_2024_width = 160          # 2024 amount column width

# Typography
title_font_size = 14
heading_font_size = 12
body_font_size = 10
header_font_size = 9

# Spacing
section_spacing = 12               # Space between sections
row_padding = 6                    # Padding inside cells
note_indent = 20                   # Indent for note content

# Colors
header_bg_color = (0.8, 0.8, 0.8) # Light gray
border_color = (0, 0, 0)          # Black
text_color = (0, 0, 0)            # Black
```

---

## WORKFLOW: How We Fine-Tune

### Phase 1: Change Page Size (1-2 hours)

```python
# In format_applier.py, around line 386:

# BEFORE:
from reportlab.lib import pagesizes
pagesize = pagesizes.A4  # 595 × 841.89

# AFTER:
pagesize = (612, 792)    # US Letter

# Run: python generate_test_pdf.py
# Compare: Generated PDF page 1 vs Reference PDF page 1
# Result: Should see ~14% more width available
```

**What happens:**
- ReportLab automatically recalculates column widths
- Tables spread out to use more horizontal space
- Row heights might adjust
- Page breaks change (fewer pages overall)

---

### Phase 2: Adjust Column Widths (2-4 hours)

```python
# Reference PDF measured: column widths are 170, 160, 160
# Our generated PDF currently: 165, 155, 155

# In format_applier.py, find table definition:

# BEFORE:
table_data = [
    [Paragraph("Account", style), 
     Paragraph("2025", style),
     Paragraph("2024", style)]
]
col_widths = [165, 155, 155]

# AFTER:
col_widths = [170, 160, 160]  # Adjust to match reference

# Run: python generate_test_pdf.py
# Compare: Column alignment should now match reference
# Iterate: Fine-tune more if needed
```

---

### Phase 3: Adjust Fonts & Spacing (2-4 hours)

```python
# Reference PDF uses: Arial, 10pt body, 12pt headings
# Our PDF currently: Times, 10pt body, 11pt headings

# In format_applier.py:

# BEFORE:
body_font = "Times-Roman"
body_size = 10
heading_size = 11

# AFTER:
body_font = "Helvetica"        # Match reference font
body_size = 10
heading_size = 12              # Match reference size

row_padding = 6                # Adjust cell padding
section_spacing = 14           # Adjust section gaps

# Run: python generate_test_pdf.py
# Compare: Font and spacing should now match
# Iterate: Further refinements
```

---

### Phase 4: Iterate Until Match (Variable)

```
Loop:
  1. Look at generated PDF page X
  2. Look at reference PDF page X
  3. Identify difference (spacing, alignment, font, etc.)
  4. Find the Python parameter
  5. Change parameter in format_applier.py
  6. Regenerate PDF
  7. Compare again
  8. If match → Move to next issue
  9. If not → Try different value, go to step 6
  10. When all pages match → Done!
```

---

## TOOLS INVOLVED

### ✅ **Python** (What we use for fine-tuning)
- Language: Python 3.11
- Location: `backend/core/format_applier.py` (~1400 lines)
- Purpose: Controls all PDF formatting parameters
- How: Edit .py file → Change parameters → Regenerate PDF

### ✅ **ReportLab** (Python library)
- Purpose: Renders PDF from Python code
- What it controls: Page size, fonts, tables, spacing, colors
- How: Parameters in Python code → ReportLab applies them

### ✅ **PDF Comparison** (Manual visual inspection)
- Purpose: Compare generated vs reference
- Tools: Adobe Reader, Preview, any PDF viewer
- Process: Open both PDFs side-by-side, look for differences

### ❌ **LLM** (NOT used for fine-tuning)
- Why not: LLM can't directly modify PDF layout
- LLM role: Earlier stage (extracting financial data)
- Fine-tuning: Pure Python/ReportLab, no LLM needed

---

## EXAMPLE: COMPLETE FINE-TUNING SESSION

### Start: Generate baseline PDF
```bash
cd backend
python -m core.format_applier  # Creates test PDF
```

### Check 1: Page size is wrong
```
Generated: A4 (595 width)
Reference: US Letter (612 width)
→ Edit format_applier.py line 386
  pagesize = pagesizes.A4  →  pagesize = (612, 792)
→ Regenerate
```

### Check 2: Column widths off by 5 points
```
Generated: col_widths = [165, 155, 155]
Reference: col_widths = [170, 160, 160]
→ Edit format_applier.py line 520
  col_widths = [165, 155, 155]  →  col_widths = [170, 160, 160]
→ Regenerate
```

### Check 3: Font too small
```
Generated: font_size = 10
Reference: font_size = 11
→ Edit format_applier.py line 450
  body_size = 10  →  body_size = 11
→ Regenerate
```

### Check 4: Spacing too tight
```
Generated: row_padding = 4
Reference: row_padding = 8
→ Edit format_applier.py line 480
  row_padding = 4  →  row_padding = 8
→ Regenerate
```

### Final: Compare result
```
Generated PDF page 1 vs Reference PDF page 1
→ Alignment: ✓
→ Fonts: ✓
→ Spacing: ✓
→ Page breaks: ✓
→ SUCCESS!
```

---

## WHY NOT LLM FOR FINE-TUNING?

### LLM Limitations:
```
LLM can:
  ✓ Generate text
  ✓ Analyze documents
  ✓ Extract data
  ✓ Make decisions

LLM CANNOT:
  ✗ Directly modify PDF structure
  ✗ Change pixel positions
  ✗ Adjust formatting parameters in real-time
  ✗ Render visual output
  ✗ Measure spacing precision
```

### Python/ReportLab Advantages:
```
Python can:
  ✓ Change parameters
  ✓ Regenerate PDF instantly
  ✓ Measure exact dimensions
  ✓ Control every pixel
  ✓ Iterate automatically (scripting)
  ✓ Version control changes (git)
```

---

## TOOLS YOU'LL USE

During fine-tuning, YOU will need:

1. **Text Editor** (VS Code, PyCharm)
   - Edit format_applier.py
   - Change parameters
   - Save changes

2. **Python** (command line)
   - Run: `python generate_test_pdf.py`
   - Generate new PDF after each change

3. **PDF Viewer** (Adobe Reader, Preview)
   - Open generated PDF
   - Open reference PDF
   - Compare side-by-side

4. **Git** (command line or GUI)
   - Track changes
   - Commit working versions
   - Revert if something breaks

---

## SUMMARY

| Question | Answer |
|----------|--------|
| **What are we fine-tuning?** | Python code parameters in `format_applier.py` |
| **Which LLM?** | None - fine-tuning doesn't use LLM |
| **What language?** | Python |
| **Which library?** | ReportLab (PDF generation) |
| **How do we iterate?** | Edit Python → Regenerate PDF → Compare → Repeat |
| **Can we automate?** | Yes - script PDF generation and comparison |
| **Time to 95% match?** | 1-3 days with systematic approach |
| **Tools needed?** | Text editor + Python + PDF viewer + Git |

---

## NEXT STEP

Ready to start?

1. **I set up the process** (create test script, set up comparison)
2. **You approve the approach** (do you want this exact workflow?)
3. **We begin Phase 1** (change page size A4 → US Letter)
4. **Iterate** (systematically adjust parameters)
5. **Verify** (compare with reference until matches)

Want me to proceed?
