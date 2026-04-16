"""
Format Applier — converts structured audit_report.json into PDF, DOCX, or Excel.

Takes the output of structured_report_generator.generate_audit_report() and
produces professional, download-ready financial documents.
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = {
    "columns": ["Account", "Notes", "Current Year", "Prior Year"],
    "currency_symbol": "AED",
    "font_family": "Times New Roman",
    "font_size": 10,
    "page_size": "A4",
    "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
}


def _fmt_number(value, currency: str = "AED") -> str:
    """Format a number with commas; negatives in parentheses; None as '-'."""
    if value is None:
        return "-"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "-"
    if num < 0:
        return f"({abs(num):,.2f})"
    return f"{num:,.2f}"


def _safe_get(d: dict, *keys, default=None):
    """Nested dict accessor."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


# ── Public API ────────────────────────────────────────────────────────────────


def apply_format(
    report_json: dict,
    format_template: Optional[dict] = None,
    output_format: str = "pdf",
) -> bytes:
    """
    Convert audit_report.json dict to formatted file bytes.

    Args:
        report_json: Structured audit report (from structured_report_generator).
        format_template: Optional display overrides (columns, font, margins, etc.).
        output_format: One of "pdf", "docx", "xlsx".

    Returns:
        Raw bytes of the generated document.
    """
    tpl = {**DEFAULT_TEMPLATE, **(format_template or {})}

    dispatch = {
        "pdf": _generate_pdf,
        "docx": _generate_docx,
        "xlsx": _generate_xlsx,
    }

    generator = dispatch.get(output_format.lower())
    if generator is None:
        raise ValueError(f"Unsupported output_format '{output_format}'. Use pdf, docx, or xlsx.")

    return generator(report_json, tpl)


# ══════════════════════════════════════════════════════════════════════════════
#  PDF generation (ReportLab)
# ══════════════════════════════════════════════════════════════════════════════


def _generate_pdf(report: dict, tpl: dict) -> bytes:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether,
    )

    buf = io.BytesIO()
    page_size = letter if tpl.get("page_size", "A4").upper() == "LETTER" else A4
    margins = tpl.get("margins", {})
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margins.get("left", 72),
        rightMargin=margins.get("right", 72),
        topMargin=margins.get("top", 72),
        bottomMargin=margins.get("bottom", 72),
    )

    base_font_size = tpl.get("font_size", 10)
    currency = tpl.get("currency_symbol", "AED")
    meta = report.get("metadata", {})
    company = meta.get("company_name", "Company")
    period_end = meta.get("period_end", "")
    auditor = meta.get("auditor_name", "")

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("CoverTitle", parent=styles["Title"],
                             fontSize=20, leading=24, alignment=TA_CENTER,
                             spaceAfter=6, fontName="Times-Bold")
    s_subtitle = ParagraphStyle("CoverSub", parent=styles["Normal"],
                                fontSize=13, alignment=TA_CENTER,
                                spaceAfter=4, fontName="Times-Roman")
    s_heading = ParagraphStyle("SH", parent=styles["Heading1"],
                               fontSize=13, leading=16,
                               fontName="Times-Bold", spaceAfter=8)
    s_body = ParagraphStyle("Body", parent=styles["Normal"],
                            fontSize=base_font_size, leading=base_font_size + 4,
                            fontName="Times-Roman", spaceAfter=4)
    s_section = ParagraphStyle("SectionHead", parent=s_body,
                               fontName="Times-Bold", fontSize=base_font_size)
    s_note_title = ParagraphStyle("NoteTitle", parent=s_body,
                                  fontName="Times-Bold",
                                  fontSize=base_font_size + 1, spaceBefore=8)
    s_right = ParagraphStyle("Right", parent=s_body, alignment=TA_RIGHT)

    story: list = []

    # ── Cover page ────────────────────────────────────────────────────────
    story.extend([Spacer(1, 120)])
    story.append(Paragraph(company.upper(), s_title))
    story.append(Spacer(1, 30))
    story.append(Paragraph("FINANCIAL STATEMENTS AND", s_subtitle))
    story.append(Paragraph("INDEPENDENT AUDITOR'S REPORT", s_subtitle))
    story.append(Spacer(1, 20))
    if period_end:
        story.append(Paragraph(f"FOR THE YEAR ENDED {period_end}", s_subtitle))
    if auditor:
        story.append(Spacer(1, 40))
        story.append(Paragraph(f"Auditor: {auditor}", s_subtitle))
    story.append(PageBreak())

    # ── Auditor's opinion ─────────────────────────────────────────────────
    opinion = report.get("auditor_opinion", {})
    if opinion:
        story.append(Paragraph("Independent Auditor's Report", s_heading))
        story.append(Spacer(1, 6))
        opinion_type = (opinion.get("opinion_type") or "").replace("_", " ").title()
        if opinion_type:
            story.append(Paragraph(f"<b>Opinion:</b> {opinion_type}", s_body))
        opinion_text = opinion.get("opinion_text", "")
        if opinion_text:
            story.append(Spacer(1, 4))
            story.append(Paragraph(opinion_text, s_body))

        basis = opinion.get("basis_text", "")
        if basis:
            story.append(Spacer(1, 6))
            story.append(Paragraph("<b>Basis for Opinion</b>", s_body))
            story.append(Paragraph(basis, s_body))

        for kam in opinion.get("key_audit_matters", []):
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Key Audit Matter:</b> {kam}", s_body))

        if opinion.get("going_concern"):
            story.append(Spacer(1, 6))
            story.append(Paragraph("<b>Going Concern</b>", s_body))
            gc_note = opinion.get("going_concern_note", "")
            if gc_note:
                story.append(Paragraph(gc_note, s_body))

        story.append(PageBreak())

    # ── Financial statements ──────────────────────────────────────────────
    statements = report.get("financial_statements", {})
    for stmt_key in ("statement_of_financial_position", "statement_of_profit_or_loss",
                     "statement_of_changes_in_equity", "statement_of_cash_flows"):
        stmt = statements.get(stmt_key)
        if not stmt:
            continue
        story.append(Paragraph(stmt.get("title", stmt_key.replace("_", " ").title()), s_heading))
        story.append(Paragraph(
            f"{company}  —  As at {period_end}" if "position" in stmt_key
            else f"{company}  —  For the year ended {period_end}",
            s_subtitle,
        ))
        story.append(Spacer(1, 8))

        table_data = _build_pdf_statement_table(stmt, currency, tpl)
        if table_data:
            col_widths = _calc_col_widths(page_size[0] - margins.get("left", 72) - margins.get("right", 72))
            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(_financial_table_style(len(table_data), table_data))
            story.append(t)

        story.append(PageBreak())

    # ── Notes ─────────────────────────────────────────────────────────────
    notes = report.get("notes", {})
    if notes:
        story.append(Paragraph("Notes to the Financial Statements", s_heading))
        story.append(Spacer(1, 6))

        policies = notes.get("accounting_policies", "")
        if policies:
            story.append(Paragraph("<b>Accounting Policies</b>", s_note_title))
            for para in policies.split("\n\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(para.replace("\n", "<br/>"), s_body))
            story.append(Spacer(1, 6))

        estimates = notes.get("critical_estimates", "")
        if estimates:
            story.append(Paragraph("<b>Critical Estimates and Judgements</b>", s_note_title))
            story.append(Paragraph(estimates, s_body))
            story.append(Spacer(1, 6))

        items = notes.get("items") or notes.get("sections") or []
        for item in items:
            num = item.get("note_number", "")
            title = item.get("title", "")
            content = item.get("content", "")
            story.append(Paragraph(f"<b>Note {num}: {title}</b>", s_note_title))
            for para in content.split("\n\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(para.replace("\n", "<br/>"), s_body))
            story.append(Spacer(1, 4))

    # ── Build with page numbers ───────────────────────────────────────────
    def _add_page_number(canvas, doc_ref):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(page_size[0] / 2, 30, f"— {page_num} —")
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buf.getvalue()


def _build_pdf_statement_table(stmt: dict, currency: str, tpl: dict) -> list[list[str]]:
    """Build 2-D list for a financial statement table (header + rows)."""
    cols = tpl.get("columns", DEFAULT_TEMPLATE["columns"])
    header = [cols[0], cols[1], f"{cols[2]} ({currency})", f"{cols[3]} ({currency})"]
    rows: list[list[str]] = [header]

    for section in stmt.get("sections", []):
        # Section header row
        rows.append([section.get("title", ""), "", "", ""])

        for item in section.get("line_items", []):
            rows.append([
                f"    {item.get('account_name', '')}",
                str(item.get("note_ref") or item.get("notes_ref") or ""),
                _fmt_number(item.get("current_year"), currency),
                _fmt_number(item.get("prior_year"), currency),
            ])

        sub = section.get("subtotal")
        if sub:
            rows.append([
                sub.get("account_name", ""),
                "",
                _fmt_number(sub.get("current_year"), currency),
                _fmt_number(sub.get("prior_year"), currency),
            ])

    total = stmt.get("total")
    if total:
        rows.append([
            total.get("account_name", ""),
            "",
            _fmt_number(total.get("current_year"), currency),
            _fmt_number(total.get("prior_year"), currency),
        ])

    return rows


def _calc_col_widths(available: float) -> list[float]:
    """Split available width into 4 columns: wide account col + 3 narrow cols."""
    note_w = 40
    num_w = (available - note_w) * 0.30
    acct_w = available - note_w - 2 * num_w
    return [acct_w, note_w, num_w, num_w]


def _financial_table_style(row_count: int, data: list[list[str]]):
    """Return a TableStyle for financial statement tables with proper formatting."""
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    cmds = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Align numbers right
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        # Grid lines
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
    ]

    for i, row in enumerate(data):
        if i == 0:
            continue
        cell_text = (row[0] or "").strip()

        # Section header — bold, no indent
        if cell_text and not cell_text.startswith(" ") and row[2] == "" and row[3] == "":
            cmds.append(("FONTNAME", (0, i), (0, i), "Times-Bold"))
            cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f7fa")))

        # Subtotal — single line below
        is_subtotal = cell_text.lower().startswith("total ") and i < len(data) - 1
        if is_subtotal:
            cmds.append(("FONTNAME", (0, i), (-1, i), "Times-Bold"))
            cmds.append(("LINEBELOW", (2, i), (3, i), 0.5, colors.black))

        # Grand total — double line below
        is_grand_total = cell_text.lower().startswith("total ") and i == len(data) - 1
        if is_grand_total or cell_text.lower().startswith("net profit"):
            cmds.append(("FONTNAME", (0, i), (-1, i), "Times-Bold"))
            cmds.append(("LINEABOVE", (2, i), (3, i), 0.5, colors.black))
            cmds.append(("LINEBELOW", (2, i), (3, i), 1.5, colors.black))

    return TableStyle(cmds)


# ══════════════════════════════════════════════════════════════════════════════
#  DOCX generation (python-docx)
# ══════════════════════════════════════════════════════════════════════════════


def _generate_docx(report: dict, tpl: dict) -> bytes:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn

    font_name = tpl.get("font_family", "Times New Roman")
    font_size = tpl.get("font_size", 10)
    currency = tpl.get("currency_symbol", "AED")
    meta = report.get("metadata", {})
    company = meta.get("company_name", "Company")
    period_end = meta.get("period_end", "")
    auditor = meta.get("auditor_name", "")

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Default font
    style = doc.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size)

    def _run(para, text, bold=False, size=None, color=None, italic=False):
        r = para.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.name = font_name
        r.font.size = Pt(size or font_size)
        if color:
            r.font.color.rgb = RGBColor(*color)
        return r

    # ── Cover page ────────────────────────────────────────────────────────
    for _ in range(4):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, company.upper(), bold=True, size=18)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "FINANCIAL STATEMENTS AND", bold=True, size=13)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "INDEPENDENT AUDITOR'S REPORT", bold=True, size=13)

    doc.add_paragraph()

    if period_end:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, f"FOR THE YEAR ENDED {period_end}", bold=True, size=13)

    if auditor:
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, f"Auditor: {auditor}", size=11, italic=True)

    doc.add_page_break()

    # ── Auditor's opinion ─────────────────────────────────────────────────
    opinion = report.get("auditor_opinion", {})
    if opinion:
        doc.add_heading("Independent Auditor's Report", level=1)

        opinion_type = (opinion.get("opinion_type") or "").replace("_", " ").title()
        if opinion_type:
            p = doc.add_paragraph()
            _run(p, "Opinion: ", bold=True)
            _run(p, opinion_type)

        opinion_text = opinion.get("opinion_text", "")
        if opinion_text:
            doc.add_paragraph(opinion_text)

        basis = opinion.get("basis_text", "")
        if basis:
            p = doc.add_paragraph()
            _run(p, "Basis for Opinion", bold=True)
            doc.add_paragraph(basis)

        for kam in opinion.get("key_audit_matters", []):
            p = doc.add_paragraph()
            _run(p, "Key Audit Matter: ", bold=True)
            _run(p, str(kam))

        if opinion.get("going_concern"):
            p = doc.add_paragraph()
            _run(p, "Going Concern", bold=True)
            gc_note = opinion.get("going_concern_note", "")
            if gc_note:
                doc.add_paragraph(gc_note)

        doc.add_page_break()

    # ── Financial statements ──────────────────────────────────────────────
    statements = report.get("financial_statements", {})
    for stmt_key in ("statement_of_financial_position", "statement_of_profit_or_loss",
                     "statement_of_changes_in_equity", "statement_of_cash_flows"):
        stmt = statements.get(stmt_key)
        if not stmt:
            continue

        doc.add_heading(stmt.get("title", ""), level=1)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label = (f"{company}  —  As at {period_end}" if "position" in stmt_key
                 else f"{company}  —  For the year ended {period_end}")
        _run(p, label, italic=True, size=font_size)

        cols = tpl.get("columns", DEFAULT_TEMPLATE["columns"])
        table_rows = _build_docx_statement_rows(stmt, currency)

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        hdr = table.rows[0].cells
        hdr[0].text = cols[0]
        hdr[1].text = cols[1]
        hdr[2].text = f"{cols[2]} ({currency})"
        hdr[3].text = f"{cols[3]} ({currency})"

        # Header formatting
        for cell in hdr:
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.bold = True
                    run.font.size = Pt(font_size)
                    run.font.name = font_name
            _shade_cell(cell, "D9E2F3")

        # Data rows
        for row_data in table_rows:
            row_cells = table.add_row().cells
            row_cells[0].text = row_data["account"]
            row_cells[1].text = row_data["note"]
            row_cells[2].text = row_data["current"]
            row_cells[3].text = row_data["prior"]

            is_section_header = row_data.get("is_section")
            is_subtotal = row_data.get("is_subtotal")
            is_total = row_data.get("is_total")

            for i, cell in enumerate(row_cells):
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(font_size)
                        run.font.name = font_name
                        if is_section_header or is_subtotal or is_total:
                            run.bold = True
                    if i >= 2:
                        para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

            if is_section_header:
                _shade_cell(row_cells[0], "F2F2F2")

        doc.add_paragraph()
        doc.add_page_break()

    # ── Notes ─────────────────────────────────────────────────────────────
    notes = report.get("notes", {})
    if notes:
        doc.add_heading("Notes to the Financial Statements", level=1)

        policies = notes.get("accounting_policies", "")
        if policies:
            p = doc.add_paragraph()
            _run(p, "Accounting Policies", bold=True, size=font_size + 1)
            for para_text in policies.split("\n\n"):
                para_text = para_text.strip()
                if para_text:
                    doc.add_paragraph(para_text)

        estimates = notes.get("critical_estimates", "")
        if estimates:
            p = doc.add_paragraph()
            _run(p, "Critical Estimates and Judgements", bold=True, size=font_size + 1)
            doc.add_paragraph(estimates)

        items = notes.get("items") or notes.get("sections") or []
        for item in items:
            num = item.get("note_number", "")
            title = item.get("title", "")
            content = item.get("content", "")
            doc.add_heading(f"Note {num}: {title}", level=2)
            for para_text in content.split("\n\n"):
                para_text = para_text.strip()
                if para_text:
                    doc.add_paragraph(para_text)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_docx_statement_rows(stmt: dict, currency: str) -> list[dict]:
    """Flatten statement sections into row dicts for DOCX table."""
    rows = []
    for section in stmt.get("sections", []):
        rows.append({
            "account": section.get("title", ""),
            "note": "", "current": "", "prior": "",
            "is_section": True,
        })
        for item in section.get("line_items", []):
            rows.append({
                "account": f"    {item.get('account_name', '')}",
                "note": str(item.get("note_ref") or item.get("notes_ref") or ""),
                "current": _fmt_number(item.get("current_year"), currency),
                "prior": _fmt_number(item.get("prior_year"), currency),
            })
        sub = section.get("subtotal")
        if sub:
            rows.append({
                "account": sub.get("account_name", ""),
                "note": "",
                "current": _fmt_number(sub.get("current_year"), currency),
                "prior": _fmt_number(sub.get("prior_year"), currency),
                "is_subtotal": True,
            })

    total = stmt.get("total")
    if total:
        rows.append({
            "account": total.get("account_name", ""),
            "note": "",
            "current": _fmt_number(total.get("current_year"), currency),
            "prior": _fmt_number(total.get("prior_year"), currency),
            "is_total": True,
        })
    return rows


def _shade_cell(cell, hex_color: str):
    """Apply background shading to a DOCX table cell."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), hex_color)
    shading.set(qn("w:val"), "clear")
    cell._tc.get_or_add_tcPr().append(shading)


# ══════════════════════════════════════════════════════════════════════════════
#  Excel generation (openpyxl)
# ══════════════════════════════════════════════════════════════════════════════


def _generate_xlsx(report: dict, tpl: dict) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter

    currency = tpl.get("currency_symbol", "AED")
    font_name = tpl.get("font_family", "Times New Roman")
    font_size = tpl.get("font_size", 10)
    meta = report.get("metadata", {})
    company = meta.get("company_name", "Company")
    period_end = meta.get("period_end", "")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_font = Font(name=font_name, size=font_size, bold=True)
    header_fill = PatternFill("solid", fgColor="D9E2F3")
    section_font = Font(name=font_name, size=font_size, bold=True)
    section_fill = PatternFill("solid", fgColor="F2F2F2")
    normal_font = Font(name=font_name, size=font_size)
    bold_font = Font(name=font_name, size=font_size, bold=True)
    title_font = Font(name=font_name, size=12, bold=True)
    num_fmt = '#,##0.00'
    thin_border = Border(bottom=Side(style="thin"))
    double_border = Border(bottom=Side(style="double"))

    cols = tpl.get("columns", DEFAULT_TEMPLATE["columns"])
    statements = report.get("financial_statements", {})

    sheet_map = {
        "statement_of_financial_position": "SOFP",
        "statement_of_profit_or_loss": "SOPL",
    }

    for stmt_key, sheet_name in sheet_map.items():
        stmt = statements.get(stmt_key)
        if not stmt:
            continue

        ws = wb.create_sheet(title=sheet_name)
        row_num = 1

        # Title
        ws.cell(row=row_num, column=1, value=stmt.get("title", "")).font = title_font
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
        row_num += 1

        # Subtitle
        ws.cell(row=row_num, column=1, value=f"{company}  —  {period_end}").font = Font(
            name=font_name, size=font_size, italic=True)
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
        row_num += 2

        # Header row
        headers = [cols[0], cols[1], f"{cols[2]} ({currency})", f"{cols[3]} ({currency})"]
        for c, val in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=c, value=val)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        row_num += 1

        # Data rows
        for section in stmt.get("sections", []):
            # Section header
            cell = ws.cell(row=row_num, column=1, value=section.get("title", ""))
            cell.font = section_font
            cell.fill = section_fill
            for c in range(2, 5):
                ws.cell(row=row_num, column=c).fill = section_fill
            row_num += 1

            for item in section.get("line_items", []):
                ws.cell(row=row_num, column=1, value=f"    {item.get('account_name', '')}").font = normal_font
                ws.cell(row=row_num, column=2, value=str(
                    item.get("note_ref") or item.get("notes_ref") or "")).font = normal_font
                ws.cell(row=row_num, column=2).alignment = Alignment(horizontal="center")

                _write_number_cell(ws, row_num, 3, item.get("current_year"), normal_font, num_fmt)
                _write_number_cell(ws, row_num, 4, item.get("prior_year"), normal_font, num_fmt)
                row_num += 1

            sub = section.get("subtotal")
            if sub:
                ws.cell(row=row_num, column=1, value=sub.get("account_name", "")).font = bold_font
                _write_number_cell(ws, row_num, 3, sub.get("current_year"), bold_font, num_fmt)
                _write_number_cell(ws, row_num, 4, sub.get("prior_year"), bold_font, num_fmt)
                ws.cell(row=row_num, column=3).border = thin_border
                ws.cell(row=row_num, column=4).border = thin_border
                row_num += 1

            row_num += 1  # blank row between sections

        # Grand total
        total = stmt.get("total")
        if total:
            ws.cell(row=row_num, column=1, value=total.get("account_name", "")).font = bold_font
            _write_number_cell(ws, row_num, 3, total.get("current_year"), bold_font, num_fmt)
            _write_number_cell(ws, row_num, 4, total.get("prior_year"), bold_font, num_fmt)
            ws.cell(row=row_num, column=3).border = double_border
            ws.cell(row=row_num, column=4).border = double_border

        # Column widths
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 8
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 22

    # ── Notes sheet ───────────────────────────────────────────────────────
    notes = report.get("notes", {})
    if notes:
        ws = wb.create_sheet(title="Notes")
        row_num = 1

        ws.cell(row=row_num, column=1, value="Notes to the Financial Statements").font = title_font
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3)
        row_num += 2

        # Header
        for c, val in enumerate(["Note #", "Title", "Content"], 1):
            cell = ws.cell(row=row_num, column=c, value=val)
            cell.font = header_font
            cell.fill = header_fill
        row_num += 1

        # Accounting policies row
        policies = notes.get("accounting_policies", "")
        if policies:
            ws.cell(row=row_num, column=1, value="—").font = normal_font
            ws.cell(row=row_num, column=2, value="Accounting Policies").font = bold_font
            ws.cell(row=row_num, column=3, value=policies[:500]).font = normal_font
            ws.cell(row=row_num, column=3).alignment = Alignment(wrap_text=True)
            row_num += 1

        items = notes.get("items") or notes.get("sections") or []
        for item in items:
            ws.cell(row=row_num, column=1, value=str(item.get("note_number", ""))).font = normal_font
            ws.cell(row=row_num, column=1).alignment = Alignment(horizontal="center")
            ws.cell(row=row_num, column=2, value=item.get("title", "")).font = bold_font
            ws.cell(row=row_num, column=3, value=item.get("content", "")).font = normal_font
            ws.cell(row=row_num, column=3).alignment = Alignment(wrap_text=True)
            row_num += 1

        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 30
        ws.column_dimensions["C"].width = 70

    # Ensure at least one sheet exists
    if not wb.sheetnames:
        wb.create_sheet(title="Report")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_number_cell(ws, row: int, col: int, value, font, num_fmt: str):
    """Write a numeric value to an Excel cell with proper formatting."""
    from openpyxl.styles import Alignment
    cell = ws.cell(row=row, column=col)
    if value is None:
        cell.value = "-"
        cell.font = font
        cell.alignment = Alignment(horizontal="right")
        return
    try:
        num = float(value)
        cell.value = num
        cell.number_format = num_fmt
    except (TypeError, ValueError):
        cell.value = "-"
    cell.font = font
    cell.alignment = Alignment(horizontal="right")
