"""
Comprehensive PDF Format Extractor
Extracts every formatting detail from the reference PDF and compares with generated PDF.
Saves complete format specification to format_config.json.
"""

import fitz  # PyMuPDF
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026")
REF_PDF  = BASE / "Testing data" / "Draft FS - Castle Plaza 2025.pdf"
GEN_PDF  = BASE / "Testing data" / "Castle_Plaza_Audit_2025_v3.pdf"
OUT_JSON = BASE / "Testing data" / "format_config.json"

# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def pt_to_mm(pt):
    return round(pt * 25.4 / 72, 2)

def classify_page(text: str, page_num: int) -> tuple[str, str]:
    """Return (type, description) for a page based on its text content."""
    t = text.upper()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    first_lines = ' '.join(lines[:10]).upper()

    if page_num == 0:
        return "COVER", "Cover page / Title page with company name and report date"
    if "INDEPENDENT AUDITOR" in t:
        return "AUDITOR_REPORT", "Independent Auditor's Report"
    if "STATEMENT OF FINANCIAL POSITION" in t:
        return "SOFP", "Statement of Financial Position (Balance Sheet)"
    if "STATEMENT OF PROFIT OR LOSS" in t or "STATEMENT OF COMPREHENSIVE INCOME" in t:
        return "SOPL", "Statement of Profit or Loss / Comprehensive Income"
    if "STATEMENT OF CHANGES IN EQUITY" in t:
        return "SOCE", "Statement of Changes in Equity"
    if "STATEMENT OF CASH FLOW" in t:
        return "SOCF", "Statement of Cash Flows"
    if t.startswith("NOTE") or first_lines.startswith("NOTE"):
        return "NOTE", f"Notes to Financial Statements"
    if "SIGNIFICANT ACCOUNTING" in t or "BASIS OF PREPARATION" in t:
        return "NOTE_POLICY", "Accounting Policies Note"
    if "NOTES TO" in t:
        return "NOTES_HEADER", "Notes to Financial Statements (header/intro page)"
    return "CONTENT", f"Content page ({lines[0][:60] if lines else 'unknown'})"

def extract_text_blocks_detail(page):
    """Extract all text blocks with full positioning and font info.
    Tries rawdict first; falls back to dict, then words for position-only data.
    """
    blocks = []

    # Try rawdict first (richest info)
    try:
        page_dict = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for b in page_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    blocks.append({
                        "text": text,
                        "x0": round(span["origin"][0], 2),
                        "y0": round(span["bbox"][1], 2),
                        "x1": round(span["bbox"][2], 2),
                        "y1": round(span["bbox"][3], 2),
                        "font": span.get("font", ""),
                        "size": round(span.get("size", 0), 2),
                        "flags": span.get("flags", 0),
                        "color": span.get("color", 0),
                    })
    except Exception:
        pass

    # Fall back to plain dict if rawdict found nothing
    if not blocks:
        try:
            page_dict = page.get_text("dict")
            for b in page_dict.get("blocks", []):
                if b.get("type") != 0:
                    continue
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        blocks.append({
                            "text": text,
                            "x0": round(span["bbox"][0], 2),
                            "y0": round(span["bbox"][1], 2),
                            "x1": round(span["bbox"][2], 2),
                            "y1": round(span["bbox"][3], 2),
                            "font": span.get("font", ""),
                            "size": round(span.get("size", 0), 2),
                            "flags": span.get("flags", 0),
                            "color": span.get("color", 0),
                        })
        except Exception:
            pass

    # Final fallback: word-level positions (no font info)
    if not blocks:
        try:
            for w in page.get_text("words"):
                x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
                if not text.strip():
                    continue
                blocks.append({
                    "text": text.strip(),
                    "x0": round(x0, 2),
                    "y0": round(y0, 2),
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "font": "",
                    "size": 0,
                    "flags": 0,
                    "color": 0,
                })
        except Exception:
            pass

    return blocks

def flag_description(flags: int) -> str:
    parts = []
    if flags & 2**0: parts.append("superscript")
    if flags & 2**1: parts.append("italic")
    if flags & 2**2: parts.append("serifed")
    if flags & 2**3: parts.append("monospaced")
    if flags & 2**4: parts.append("bold")
    return ",".join(parts) if parts else "regular"

def color_to_hex(color_int: int) -> str:
    """Convert fitz integer color (packed RGB) to hex string."""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"

def find_margins(blocks, page_width, page_height):
    """Estimate margins from the extreme text positions."""
    if not blocks:
        return {"top": None, "bottom": None, "left": None, "right": None}
    xs0 = [b["x0"] for b in blocks]
    xs1 = [b["x1"] for b in blocks]
    ys0 = [b["y0"] for b in blocks]
    ys1 = [b["y1"] for b in blocks]
    return {
        "top":    round(min(ys0), 2),
        "bottom": round(page_height - max(ys1), 2),
        "left":   round(min(xs0), 2),
        "right":  round(page_width - max(xs1), 2),
    }

def extract_column_positions(blocks, y_tolerance=4):
    """
    Detect columns in tabular content by clustering x0 positions of numeric-looking spans.
    Returns a sorted list of x-positions that appear frequently (candidate column starts).
    """
    x_counter = Counter()
    for b in blocks:
        txt = b["text"].strip()
        # Numeric or currency-like text
        is_numeric = any(c.isdigit() for c in txt) and len(txt) >= 3
        if is_numeric:
            x_counter[round(b["x0"] / 5) * 5] += 1  # bucket to nearest 5pt
    # Keep positions that appear at least 3 times
    cols = sorted([x for x, cnt in x_counter.items() if cnt >= 3])
    return cols

def draw_lines_info(page):
    """Extract drawn lines / rectangles (table borders)."""
    drawings = page.get_drawings()
    lines = []
    rects = []
    for d in drawings:
        for item in d.get("items", []):
            kind = item[0]
            stroke_w = d.get("width") or 0.5
            stroke_color = "#000000"
            if d.get("color"):
                try:
                    clr = d["color"]
                    if isinstance(clr, (list, tuple)) and len(clr) >= 3:
                        stroke_color = f"#{int(clr[0]*255):02X}{int(clr[1]*255):02X}{int(clr[2]*255):02X}"
                except Exception:
                    pass

            if kind == "l":  # line
                p1, p2 = item[1], item[2]
                lines.append({
                    "x0": round(p1.x, 1), "y0": round(p1.y, 1),
                    "x1": round(p2.x, 1), "y1": round(p2.y, 1),
                    "width": round(stroke_w, 2),
                    "color": stroke_color,
                })
            elif kind == "re":  # rectangle
                r = item[1]
                rects.append({
                    "x0": round(r.x0, 1), "y0": round(r.y0, 1),
                    "x1": round(r.x1, 1), "y1": round(r.y1, 1),
                    "width": round(stroke_w, 2),
                })
    return lines, rects

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ANALYSIS FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def analyze_pdf(pdf_path: Path, label: str) -> dict:
    print(f"\n{'='*100}")
    print(f"  ANALYZING: {label}")
    print(f"  File: {pdf_path.name}")
    print(f"{'='*100}")

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    file_size_kb = round(pdf_path.stat().st_size / 1024, 1)

    # ── Page dimensions ──────────────────────────────────────────────────────
    first_page = doc[0]
    page_w = round(first_page.rect.width, 2)
    page_h = round(first_page.rect.height, 2)
    # Detect standard size
    size_name = "CUSTOM"
    if abs(page_w - 595) < 5 and abs(page_h - 842) < 5:
        size_name = "A4"
    elif abs(page_w - 612) < 5 and abs(page_h - 792) < 5:
        size_name = "US_LETTER"
    elif abs(page_w - 842) < 5 and abs(page_h - 1190) < 5:
        size_name = "A3"

    print(f"\n📏 Page: {page_w} x {page_h} pt  ({pt_to_mm(page_w)} x {pt_to_mm(page_h)} mm)  → {size_name}")
    print(f"📦 File size: {file_size_kb} KB   |   Pages: {total_pages}")

    # ── Collect all fonts across entire document ─────────────────────────────
    all_fonts = defaultdict(list)  # font_name -> list of sizes
    all_colors = Counter()
    global_margin_candidates = {"left": [], "right": [], "top": [], "bottom": []}

    # ── Per-page analysis ─────────────────────────────────────────────────────
    pages_info = []
    financial_table_pages = []  # pages with tables for col extraction
    header_footer_samples = {"header": [], "footer": []}

    for pnum in range(total_pages):
        page = doc[pnum]
        text_plain = page.get_text()
        blocks = extract_text_blocks_detail(page)
        lines, rects = draw_lines_info(page)

        page_type, page_desc = classify_page(text_plain, pnum)

        # Fonts on this page
        page_fonts = Counter()
        for b in blocks:
            key = (b["font"], round(b["size"]))
            page_fonts[key] += 1
            all_fonts[b["font"]].append(b["size"])
            if b["color"] != 0:
                all_colors[color_to_hex(b["color"])] += 1

        # Margins
        margin = find_margins(blocks, page_w, page_h)

        # If blocks were empty, try HTML-based position extraction for margins
        if not blocks:
            try:
                import re as _re
                html = page.get_text("html")
                # Look for positioned div/span with top/left CSS
                lefts  = [float(m) for m in _re.findall(r'left:(\d+(?:\.\d+)?)pt', html)]
                tops   = [float(m) for m in _re.findall(r'top:(\d+(?:\.\d+)?)pt', html)]
                widths = [float(m) for m in _re.findall(r'width:(\d+(?:\.\d+)?)pt', html)]
                if lefts:
                    ml = min(lefts)
                    mr = page_w - max(l + w for l, w in zip(lefts, widths) if w > 0) if widths else None
                    mt = min(tops) if tops else None
                    # bottom is harder without heights, approximate
                    margin = {
                        "top":    round(mt, 2) if mt is not None else margin["top"],
                        "bottom": margin["bottom"],
                        "left":   round(ml, 2),
                        "right":  round(mr, 2) if mr is not None else margin["right"],
                    }
            except Exception:
                pass
        for side in ["left", "right", "top", "bottom"]:
            if margin[side] is not None:
                global_margin_candidates[side].append(margin[side])

        # Row height estimation for financial tables
        row_heights = []
        if page_type in ("SOFP", "SOPL", "SOCE", "SOCF") or "NOTE" in page_type:
            financial_table_pages.append(pnum)
            # Cluster y0 positions to get row heights
            ys = sorted(set(round(b["y0"]) for b in blocks))
            for i in range(1, len(ys)):
                gap = ys[i] - ys[i-1]
                if 8 <= gap <= 30:
                    row_heights.append(gap)

        # Header / footer detection (top 60pt = header, bottom 60pt = footer)
        header_blocks = [b for b in blocks if b["y0"] < 60]
        footer_blocks = [b for b in blocks if b["y1"] > page_h - 60]
        if header_blocks:
            header_footer_samples["header"].append({
                "page": pnum + 1,
                "text": " | ".join(b["text"] for b in header_blocks[:5]),
                "y": header_blocks[0]["y0"],
                "font": header_blocks[0]["font"],
                "size": header_blocks[0]["size"],
            })
        if footer_blocks:
            header_footer_samples["footer"].append({
                "page": pnum + 1,
                "text": " | ".join(b["text"] for b in footer_blocks[:5]),
                "y": footer_blocks[0]["y0"],
                "font": footer_blocks[0]["font"],
                "size": footer_blocks[0]["size"],
            })

        # Column detection for financial pages
        col_positions = []
        if page_type in ("SOFP", "SOPL", "SOCE", "SOCF"):
            col_positions = extract_column_positions(blocks)

        # Content summary (first meaningful lines)
        content_lines = [l.strip() for l in text_plain.split('\n') if l.strip()]
        content_summary = " | ".join(content_lines[:8])[:200]

        # Top fonts on page
        top_fonts = [{"font": k[0], "size": k[1], "count": v}
                     for k, v in page_fonts.most_common(5)]

        page_info = {
            "page_num": pnum + 1,
            "type": page_type,
            "description": page_desc,
            "content_summary": content_summary,
            "char_count": len(text_plain),
            "block_count": len(blocks),
            "margins": margin,
            "fonts_used": top_fonts,
            "col_positions_pt": col_positions,
            "row_heights_pt": sorted(set(row_heights))[:10] if row_heights else [],
            "drawn_lines": len(lines),
            "drawn_rects": len(rects),
        }
        pages_info.append(page_info)

        # Console summary
        print(f"  P{pnum+1:02d} [{page_type:18s}] "
              f"chars={len(text_plain):5d}  blocks={len(blocks):3d}  "
              f"lines={len(lines):3d}  rects={len(rects):3d}  "
              f"| {content_lines[0][:60] if content_lines else '(empty)'}")

    # ── Global font catalogue ─────────────────────────────────────────────────
    font_catalogue = {}
    for fname, sizes in all_fonts.items():
        avg_size = round(sum(sizes) / len(sizes), 1)
        common_size = Counter(round(s, 1) for s in sizes).most_common(1)[0][0]
        is_bold   = "bold" in fname.lower() or "Bold" in fname
        is_italic = "italic" in fname.lower() or "Italic" in fname or "Oblique" in fname
        font_catalogue[fname] = {
            "occurrences": len(sizes),
            "most_common_size": common_size,
            "avg_size": avg_size,
            "min_size": round(min(sizes), 1),
            "max_size": round(max(sizes), 1),
            "bold": is_bold,
            "italic": is_italic,
        }

    # Sort fonts by occurrence
    font_catalogue = dict(sorted(font_catalogue.items(),
                                 key=lambda x: x[1]["occurrences"], reverse=True))

    # ── If font catalogue is still empty, use page.get_fonts() for font names ──
    if not font_catalogue:
        all_page_fonts = []
        for pnum in range(total_pages):
            page = doc[pnum]
            for f in page.get_fonts(full=True):
                # f = (xref, ext, type, basefont, name, encoding, referencer)
                fname = f[3] if f[3] else f[4]
                if fname:
                    all_page_fonts.append(fname)
        font_counter = Counter(all_page_fonts)
        for fname, cnt in font_counter.items():
            is_bold   = "bold" in fname.lower() or "Bold" in fname
            is_italic = "italic" in fname.lower() or "Italic" in fname
            font_catalogue[fname] = {
                "occurrences": cnt,
                "most_common_size": 10.0,   # unknown without spans
                "avg_size": 10.0,
                "min_size": 0,
                "max_size": 0,
                "bold": is_bold,
                "italic": is_italic,
                "note": "size unknown (no span data)",
            }
        font_catalogue = dict(sorted(font_catalogue.items(),
                                     key=lambda x: x[1]["occurrences"], reverse=True))

    # ── Try to refine font sizes via text-extraction with html output ──────────
    # For PDFs where rawdict/dict gives no spans, try extracting font sizes
    # from the HTML rendering which may carry size in CSS
    if all(info.get("note") == "size unknown (no span data)" for info in font_catalogue.values()):
        try:
            import re as _re
            size_hits = defaultdict(list)
            for pnum in range(min(10, total_pages)):
                html = doc[pnum].get_text("html")
                # patterns like: font-size:10pt or font-size:10.5pt
                for m in _re.finditer(r'font-size:(\d+(?:\.\d+)?)pt[^>]*>(.*?)</span', html, _re.DOTALL):
                    sz = float(m.group(1))
                    txt = m.group(2)[:50]
                    size_hits[sz].append(txt)
            # assign sizes back to catalogue entries by rank
            size_by_freq = Counter({sz: len(txts) for sz, txts in size_hits.items()})
            all_sizes = [sz for sz, _ in size_by_freq.most_common()]
            fnames = list(font_catalogue.keys())
            for i, fname in enumerate(fnames):
                if i < len(all_sizes):
                    font_catalogue[fname]["most_common_size"] = all_sizes[i]
                    font_catalogue[fname]["avg_size"] = all_sizes[i]
                    del font_catalogue[fname]["note"]
        except Exception:
            pass

    # ── Global margins (median across pages) ─────────────────────────────────
    def median(lst):
        if not lst: return None
        s = sorted(lst)
        n = len(s)
        return round(s[n // 2], 2)

    global_margins = {
        side: median(vals) for side, vals in global_margin_candidates.items()
    }

    # ── Financial table column analysis ──────────────────────────────────────
    # Aggregate column x-positions across all financial table pages
    all_col_x = []
    for pnum in financial_table_pages:
        all_col_x.extend(pages_info[pnum]["col_positions_pt"])
    col_counter = Counter(all_col_x)
    frequent_cols = sorted([x for x, c in col_counter.items() if c >= 2])

    # ── Row height statistics ─────────────────────────────────────────────────
    all_row_heights = []
    for pi in pages_info:
        all_row_heights.extend(pi["row_heights_pt"])
    rh_counter = Counter(all_row_heights)
    common_row_heights = rh_counter.most_common(5)

    # ── Header / footer summary ───────────────────────────────────────────────
    hf_summary = {}
    if header_footer_samples["header"]:
        hs = header_footer_samples["header"]
        hf_summary["header_present"] = True
        hf_summary["header_y_range"] = [min(h["y"] for h in hs), max(h["y"] for h in hs)]
        hf_summary["header_font_sample"] = hs[0]["font"]
        hf_summary["header_size_sample"] = hs[0]["size"]
        hf_summary["header_text_sample"] = hs[0]["text"][:100]
    else:
        hf_summary["header_present"] = False

    if header_footer_samples["footer"]:
        fs = header_footer_samples["footer"]
        hf_summary["footer_present"] = True
        hf_summary["footer_y_range"] = [min(f["y"] for f in fs), max(f["y"] for f in fs)]
        hf_summary["footer_font_sample"] = fs[0]["font"]
        hf_summary["footer_size_sample"] = fs[0]["size"]
        hf_summary["footer_text_sample"] = fs[0]["text"][:100]
    else:
        hf_summary["footer_present"] = False

    # ── Color summary ─────────────────────────────────────────────────────────
    color_summary = dict(all_colors.most_common(10))

    # ── Line spacing (from body text blocks) ─────────────────────────────────
    body_font_sizes = []
    for fname, info in font_catalogue.items():
        if 9 <= info["most_common_size"] <= 12 and not info["bold"]:
            body_font_sizes.append(info["most_common_size"])
    body_size = body_font_sizes[0] if body_font_sizes else 10.0

    # Estimate line spacing ratio (leading / font size)
    standard_leading = common_row_heights[0][0] if common_row_heights else (body_size * 1.2)
    line_spacing_ratio = round(standard_leading / body_size, 2) if body_size else 1.2

    # ── Fonts classified by role ──────────────────────────────────────────────
    def pick_font(target_bold, size_range, fallback_size=None):
        candidates = [(fn, info) for fn, info in font_catalogue.items()
                      if info["bold"] == target_bold
                      and size_range[0] <= info["most_common_size"] <= size_range[1]]
        if not candidates:
            # relax bold constraint
            candidates = [(fn, info) for fn, info in font_catalogue.items()
                          if size_range[0] <= info["most_common_size"] <= size_range[1]]
        if not candidates:
            # relax everything – just pick most common font
            candidates = list(font_catalogue.items())
        if not candidates:
            return {"family": "Helvetica", "size": fallback_size or 10, "bold": target_bold}
        # Pick most common
        best = max(candidates, key=lambda x: x[1]["occurrences"])
        return {"family": best[0], "size": best[1]["most_common_size"], "bold": best[1]["bold"]}

    fonts_by_role = {
        "heading":    pick_font(True,  (13, 22)),
        "subheading": pick_font(True,  (10, 13)),
        "body":       pick_font(False, (8,  12)),
        "footer":     pick_font(False, (6,  9)),
        "table_header": pick_font(True, (8, 12)),
    }

    # ── Assemble result ───────────────────────────────────────────────────────
    result = {
        "source_file": str(pdf_path),
        "file_size_kb": file_size_kb,
        "total_pages": total_pages,
        "page": {
            "width_pt": page_w,
            "height_pt": page_h,
            "width_mm": pt_to_mm(page_w),
            "height_mm": pt_to_mm(page_h),
            "size_name": size_name,
        },
        "margins": global_margins,
        "fonts_catalogue": font_catalogue,
        "fonts_by_role": fonts_by_role,
        "header_footer": hf_summary,
        "colors": color_summary,
        "tables": {
            "frequent_col_x_positions": frequent_cols,
            "common_row_heights": [{"height": rh, "freq": cnt} for rh, cnt in common_row_heights],
            "estimated_label_col_width": (frequent_cols[1] - frequent_cols[0]) if len(frequent_cols) >= 2 else None,
            "estimated_value_col_width": (frequent_cols[-1] - frequent_cols[-2]) if len(frequent_cols) >= 2 else None,
        },
        "line_spacing": {
            "body_font_size": body_size,
            "standard_row_height": common_row_heights[0][0] if common_row_heights else None,
            "line_spacing_ratio": line_spacing_ratio,
        },
        "pages": pages_info,
    }

    doc.close()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def compare_analyses(ref: dict, gen: dict) -> dict:
    diffs = {}

    # Page count
    diffs["page_count"] = {
        "reference": ref["total_pages"],
        "generated": gen["total_pages"],
        "difference": ref["total_pages"] - gen["total_pages"],
    }

    # Page dimensions
    diffs["page_size"] = {
        "ref_width": ref["page"]["width_pt"],
        "ref_height": ref["page"]["height_pt"],
        "gen_width": gen["page"]["width_pt"],
        "gen_height": gen["page"]["height_pt"],
        "match": (abs(ref["page"]["width_pt"] - gen["page"]["width_pt"]) < 2 and
                  abs(ref["page"]["height_pt"] - gen["page"]["height_pt"]) < 2),
    }

    # Margins
    margin_diffs = {}
    for side in ["top", "bottom", "left", "right"]:
        rv = ref["margins"].get(side)
        gv = gen["margins"].get(side)
        if rv and gv:
            margin_diffs[side] = {
                "reference": rv, "generated": gv,
                "diff": round(rv - gv, 2),
                "match": abs(rv - gv) < 5,
            }
    diffs["margins"] = margin_diffs

    # Fonts
    ref_body = ref["fonts_by_role"].get("body", {})
    gen_body = gen["fonts_by_role"].get("body", {})
    diffs["fonts"] = {
        "body_font_ref": ref_body.get("family"),
        "body_font_gen": gen_body.get("family"),
        "body_size_ref": ref_body.get("size"),
        "body_size_gen": gen_body.get("size"),
        "body_match": ref_body.get("family") == gen_body.get("family"),
    }

    # Page type comparison
    ref_types = [p["type"] for p in ref["pages"]]
    gen_types = [p["type"] for p in gen["pages"]]
    diffs["page_structure"] = {
        "ref_types": ref_types,
        "gen_types": gen_types,
        "missing_from_gen": [t for t in ref_types if t not in gen_types],
        "extra_in_gen": [t for t in gen_types if t not in ref_types],
    }

    # Row height
    ref_rh = ref["line_spacing"].get("standard_row_height")
    gen_rh = gen["line_spacing"].get("standard_row_height")
    diffs["row_height"] = {
        "reference": ref_rh, "generated": gen_rh,
        "diff": round(ref_rh - gen_rh, 2) if ref_rh and gen_rh else None,
    }

    return diffs


# ─────────────────────────────────────────────────────────────────────────────
# FINAL CONFIG BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_format_config(ref: dict) -> dict:
    """Build the final format_config.json from the reference PDF analysis."""
    r = ref

    # Determine primary and secondary colors
    primary   = "#000000"
    secondary = "#666666"
    border    = "#000000"
    colors = r.get("colors", {})
    if colors:
        non_black = [c for c in colors if c.upper() not in ("#000000", "#FFFFFF", "#000")]
        if non_black:
            secondary = non_black[0]

    # Tables: compute column widths from col positions
    cols = r["tables"]["frequent_col_x_positions"]
    margins_left  = r["margins"].get("left", 72) or 72
    margins_right = r["margins"].get("right", 72) or 72
    usable_width  = r["page"]["width_pt"] - margins_left - margins_right

    label_col  = round(cols[0] - margins_left, 1) if len(cols) >= 1 else round(usable_width * 0.50, 1)
    notes_col  = round((cols[1] - cols[0]) if len(cols) >= 2 else 40, 1)
    value_col  = round((cols[2] - cols[1]) if len(cols) >= 3 else usable_width * 0.20, 1)

    rh_list = r["tables"]["common_row_heights"]
    row_height        = rh_list[0]["height"] if rh_list else 14
    header_row_height = round(row_height * 1.3, 1)

    fonts_role = r["fonts_by_role"]

    config = {
        "page": {
            "width_pt": r["page"]["width_pt"],
            "height_pt": r["page"]["height_pt"],
            "width_mm": r["page"]["width_mm"],
            "height_mm": r["page"]["height_mm"],
            "size_name": r["page"]["size_name"],
        },
        "margins": {
            "top":    r["margins"].get("top", 72),
            "bottom": r["margins"].get("bottom", 72),
            "left":   r["margins"].get("left", 72),
            "right":  r["margins"].get("right", 72),
        },
        "fonts": {
            "heading": {
                "family": fonts_role["heading"]["family"],
                "size":   fonts_role["heading"]["size"],
                "bold":   True,
            },
            "subheading": {
                "family": fonts_role["subheading"]["family"],
                "size":   fonts_role["subheading"]["size"],
                "bold":   True,
            },
            "body": {
                "family": fonts_role["body"]["family"],
                "size":   fonts_role["body"]["size"],
                "bold":   False,
            },
            "footer": {
                "family": fonts_role["footer"]["family"],
                "size":   fonts_role["footer"]["size"],
                "bold":   False,
            },
            "table_header": {
                "family": fonts_role["table_header"]["family"],
                "size":   fonts_role["table_header"]["size"],
                "bold":   True,
            },
        },
        "tables": {
            "financial_table": {
                "label_col_width":      label_col,
                "notes_col_width":      notes_col,
                "value_col_width":      value_col,
                "col_padding":          6,
                "row_height":           row_height,
                "header_row_height":    header_row_height,
                "frequent_col_x_pts":   cols,
            },
        },
        "header_footer": r["header_footer"],
        "colors": {
            "primary":   primary,
            "secondary": secondary,
            "border":    border,
            "all_detected": r["colors"],
        },
        "line_spacing": r["line_spacing"]["line_spacing_ratio"],
        "section_gap": round(row_height * 1.5, 1),
        "body_font_size": r["line_spacing"]["body_font_size"],
        "standard_row_height": r["line_spacing"]["standard_row_height"],
        "usable_width_pt": usable_width,
        "pages": r["pages"],
        "full_font_catalogue": r["fonts_catalogue"],
        "total_pages": r["total_pages"],
        "file_size_kb": r["file_size_kb"],
    }
    return config


# ─────────────────────────────────────────────────────────────────────────────
# PRINT SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(ref: dict, gen: dict, diffs: dict, config: dict):
    sep = "─" * 100

    print(f"\n\n{'█'*100}")
    print("█" + "  EXTRACTION SUMMARY  ".center(98) + "█")
    print(f"{'█'*100}")

    print(f"\n{sep}")
    print("  KEY MEASUREMENTS (from REFERENCE PDF)")
    print(sep)
    p = config["page"]
    m = config["margins"]
    print(f"  Page size     : {p['width_pt']} × {p['height_pt']} pt  "
          f"({p['width_mm']} × {p['height_mm']} mm)  [{p['size_name']}]")
    print(f"  Margins       : Top={m['top']}pt  Bottom={m['bottom']}pt  "
          f"Left={m['left']}pt  Right={m['right']}pt")
    print(f"  Usable width  : {config['usable_width_pt']} pt")
    print(f"  Total pages   : {ref['total_pages']}")

    print(f"\n  Fonts:")
    for role, info in config["fonts"].items():
        print(f"    {role:15s}: {info['family']}  size={info['size']}  "
              f"{'BOLD' if info.get('bold') else 'regular'}")

    t = config["tables"]["financial_table"]
    print(f"\n  Financial table columns:")
    print(f"    Label col    : {t['label_col_width']} pt")
    print(f"    Notes col    : {t['notes_col_width']} pt")
    print(f"    Value col    : {t['value_col_width']} pt")
    print(f"    Row height   : {t['row_height']} pt")
    print(f"    Header height: {t['header_row_height']} pt")
    print(f"    Col X starts : {t['frequent_col_x_pts']}")

    ls = config["line_spacing"]
    print(f"\n  Line spacing  : {ls}")
    print(f"  Section gap   : {config['section_gap']} pt")
    print(f"  Body font size: {config['body_font_size']} pt")

    if config["header_footer"].get("header_present"):
        hf = config["header_footer"]
        print(f"\n  Header: '{hf['header_text_sample']}'")
        print(f"          font={hf['header_font_sample']}  size={hf['header_size_sample']}")
    if config["header_footer"].get("footer_present"):
        hf = config["header_footer"]
        print(f"  Footer: '{hf['footer_text_sample']}'")
        print(f"          font={hf['footer_font_sample']}  size={hf['footer_size_sample']}")

    print(f"\n{sep}")
    print("  PAGE INVENTORY (Reference PDF)")
    print(sep)
    for pi in ref["pages"]:
        print(f"  P{pi['page_num']:02d}  [{pi['type']:18s}]  {pi['description'][:70]}")
        print(f"       → {pi['content_summary'][:90]}")

    print(f"\n{sep}")
    print("  MAIN DIFFERENCES: REFERENCE  vs  GENERATED")
    print(sep)

    ps = diffs["page_size"]
    match = "✅ MATCH" if ps["match"] else "❌ MISMATCH"
    print(f"  Page size  : Ref={ps['ref_width']}×{ps['ref_height']}  "
          f"Gen={ps['gen_width']}×{ps['gen_height']}  {match}")

    pc = diffs["page_count"]
    match = "✅ MATCH" if pc["difference"] == 0 else f"❌ REF has {pc['difference']:+d} pages"
    print(f"  Page count : Ref={pc['reference']}  Gen={pc['generated']}  {match}")

    for side, info in diffs["margins"].items():
        match = "✅" if info["match"] else f"❌ diff={info['diff']:+.1f}pt"
        print(f"  Margin {side:6s}: Ref={info['reference']}  Gen={info['generated']}  {match}")

    f = diffs["fonts"]
    match = "✅ MATCH" if f["body_match"] else "❌ DIFFERENT"
    print(f"  Body font  : Ref={f['body_font_ref']}@{f['body_size_ref']}  "
          f"Gen={f['body_font_gen']}@{f['body_size_gen']}  {match}")

    rh = diffs["row_height"]
    if rh["diff"] is not None:
        match = "✅" if abs(rh["diff"]) < 2 else f"❌ diff={rh['diff']:+.1f}pt"
        print(f"  Row height : Ref={rh['reference']}  Gen={rh['generated']}  {match}")

    ps_struct = diffs["page_structure"]
    if ps_struct["missing_from_gen"]:
        print(f"  Missing page types in generated: {ps_struct['missing_from_gen']}")
    if ps_struct["extra_in_gen"]:
        print(f"  Extra page types in generated  : {ps_struct['extra_in_gen']}")

    print(f"\n{sep}")
    print("  WHAT NEEDS TO CHANGE")
    print(sep)
    issues = []
    if not diffs["page_size"]["match"]:
        issues.append(f"  ❌ Change page size to {ref['page']['size_name']} "
                      f"({ref['page']['width_pt']}×{ref['page']['height_pt']} pt)")
    if diffs["page_count"]["difference"] != 0:
        issues.append(f"  ❌ Generated PDF has {diffs['page_count']['generated']} pages; "
                      f"reference has {diffs['page_count']['reference']} — add/remove pages")
    for side, info in diffs["margins"].items():
        if not info["match"]:
            issues.append(f"  ❌ Adjust {side} margin: {info['generated']}→{info['reference']} pt")
    if not diffs["fonts"]["body_match"]:
        issues.append(f"  ❌ Change body font from '{diffs['fonts']['body_font_gen']}' "
                      f"to '{diffs['fonts']['body_font_ref']}'")
    if diffs["row_height"]["diff"] and abs(diffs["row_height"]["diff"]) >= 2:
        issues.append(f"  ❌ Adjust row height from {diffs['row_height']['generated']} "
                      f"to {diffs['row_height']['reference']} pt")
    if not issues:
        issues.append("  ✅ No major structural differences detected — check content/data")
    for issue in issues:
        print(issue)

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "█"*100)
    print("█" + "  COMPREHENSIVE PDF FORMAT EXTRACTOR  ".center(98) + "█")
    print("█"*100)

    # Check files exist
    for path, name in [(REF_PDF, "Reference"), (GEN_PDF, "Generated")]:
        if not path.exists():
            print(f"\n❌ {name} PDF not found: {path}")
            sys.exit(1)
    print(f"\n  Reference : {REF_PDF}")
    print(f"  Generated : {GEN_PDF}")
    print(f"  Output    : {OUT_JSON}\n")

    # Analyze both PDFs
    ref_analysis = analyze_pdf(REF_PDF, "REFERENCE PDF")
    gen_analysis = analyze_pdf(GEN_PDF, "GENERATED PDF")

    # Compare
    diffs = compare_analyses(ref_analysis, gen_analysis)

    # Build format config
    config = build_format_config(ref_analysis)

    # Add comparison data to config
    config["comparison"] = {
        "generated_pdf": str(GEN_PDF),
        "differences": diffs,
    }

    # Save JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n✅ Saved format_config.json → {OUT_JSON}")
    print(f"   JSON size: {OUT_JSON.stat().st_size / 1024:.1f} KB")

    # Print human-readable summary
    print_summary(ref_analysis, gen_analysis, diffs, config)


if __name__ == "__main__":
    main()
