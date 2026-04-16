# FINE-TUNING TOOLS - VISUAL SUMMARY

## The Answer to Your Question

**Q: We are fine-tuning what? LLM Python or what?**

**A: PYTHON (not LLM)**

---

## WORKFLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM PHASE (Already Done)                 │
│                                                              │
│  Input PDFs (Scanned 2024, TB 2025) → LLM Extracts Data    │
│  Output: Structured JSON with financial figures            │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────┐
│                  PYTHON FINE-TUNING PHASE (Future)          │
│                                                              │
│  format_applier.py                                          │
│  ├─ Load extracted data (from LLM)                          │
│  ├─ Read parameters:                                        │
│  │  ├─ pagesize = (612, 792)                               │
│  │  ├─ margins = (50, 50)                                  │
│  │  ├─ column_widths = [170, 160, 160]                    │
│  │  ├─ font_size = 10                                      │
│  │  ├─ spacing = 12                                        │
│  │  └─ ... (20+ parameters)                               │
│  ├─ Generate PDF                                           │
│  └─ Output: PDF file                                       │
│                                                              │
│  YOUR ROLE: Adjust parameters to match reference           │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────┐
│                    ITERATION LOOP (You Do This)             │
│                                                              │
│  1. Open generated PDF + reference PDF side-by-side        │
│  2. Spot difference (e.g., column too narrow)              │
│  3. Edit format_applier.py parameter                       │
│  4. Run: python generate_test_pdf.py                      │
│  5. Compare new PDF to reference                           │
│  6. If better → continue                                   │
│  7. If not → try different value                           │
│  8. Repeat until match ✓                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## WHAT YOU'LL BE EDITING

```python
# File: backend/core/format_applier.py
# You will edit these PARAMETERS (numbers, not logic)

# PAGE SETUP
pagesize = (612, 792)                    # ← CHANGE: 595,841.89 → 612,792

# MARGINS
left_margin = 50                          # ← CHANGE: if needed
right_margin = 50                         # ← CHANGE: if needed
top_margin = 50                           # ← CHANGE: if needed
bottom_margin = 50                        # ← CHANGE: if needed

# COLUMN WIDTHS (for financial statement tables)
col_account_width = 200                   # ← CHANGE: adjust to match reference
col_amount_2025_width = 160               # ← CHANGE: adjust to match reference  
col_amount_2024_width = 160               # ← CHANGE: adjust to match reference

# FONTS
header_font_size = 12                     # ← CHANGE: if reference uses different size
body_font_size = 10                       # ← CHANGE: if reference uses different size
note_font_size = 9                        # ← CHANGE: if reference uses different size

# SPACING
section_spacing = 12                      # ← CHANGE: adjust vertical space
row_padding = 6                           # ← CHANGE: adjust cell padding
line_spacing = 1.2                        # ← CHANGE: adjust text line spacing

# COLORS (probably won't change, but could)
header_bg_color = (0.8, 0.8, 0.8)        # ← Light gray background
text_color = (0, 0, 0)                   # ← Black text
```

---

## TOOLS YOU'LL USE

```
┌──────────────────────────┐
│   Text Editor            │
│   (VS Code, PyCharm)     │
│                          │
│   Edit format_aplier.py  │
│   Change parameters      │
│   Save file              │
└──────────┬───────────────┘
           │
           ↓
┌──────────────────────────┐
│   Python Interpreter    │
│   (Command line)        │
│                          │
│   Run: python generate  │
│        _test_pdf.py    │
│   Creates new PDF       │
└──────────┬───────────────┘
           │
           ↓
┌──────────────────────────┐
│   PDF Viewer            │
│   (Adobe, Preview)      │
│                          │
│   Open generated.pdf    │
│   Open reference.pdf    │
│   Compare side-by-side  │
│   Spot differences      │
└──────────┬───────────────┘
           │
           ↓ (Differences found?)
           │
        YES → Go back to Text Editor
        NO  → Done! ✓
```

---

## THE ITERATION CYCLE

```
Cycle 1:
  Edit → Generate → Compare
  Difference: Columns too narrow
  Change: col_width 165 → 170
  
Cycle 2:
  Edit → Generate → Compare
  Difference: Font too small
  Change: font_size 10 → 11
  
Cycle 3:
  Edit → Generate → Compare
  Difference: Spacing too tight
  Change: row_padding 4 → 8
  
Cycle 4:
  Edit → Generate → Compare
  Difference: None found!
  Status: ✓ MATCH
  
Cycle 5:
  Commit to git
  Done!
```

---

## NOT USING LLM FOR THIS BECAUSE:

| Task | Tool | Why |
|------|------|-----|
| **Extract financial data** | LLM | LLM is good at understanding documents |
| **Generate formatted text** | LLM | LLM is good at creating content |
| **Fine-tune layout** | Python | Python controls exact pixel positions |
| **Change column widths** | Python | LLM can't modify ReportLab parameters |
| **Adjust fonts** | Python | LLM can't render PDFs |
| **Iterate quickly** | Python | Python regenerates instantly |

---

## YOUR INVOLVEMENT

### What YOU do:
✅ Look at generated PDF vs reference  
✅ Spot differences (e.g., "columns are 5 points too narrow")  
✅ Tell me to adjust (or adjust yourself in Python file)  
✅ Compare new PDF  
✅ Repeat until match  

### What I can automate:
✅ Create comparison script  
✅ Set up test PDF generation  
✅ Track which parameters changed  
✅ Revert changes if something breaks  
✅ Commit working versions to git  

---

## READY?

This is a straightforward process:

1. **I prepare the setup** (test script, comparison framework)
2. **We start Phase 1** (change A4 → US Letter)
3. **You guide** (spot differences in PDFs)
4. **We iterate** (adjust Python parameters)
5. **We verify** (compare until match)

**Total effort**: 1-3 days of systematic iteration

**Skills needed**: Can you:
- Edit a Python file and save it?
- Open two PDFs and compare them side-by-side?
- Report what you see (e.g., "columns are too narrow")?

If yes → We can proceed!

Want to start?
