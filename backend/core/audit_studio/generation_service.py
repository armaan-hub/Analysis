"""Generation service — dispatches per output_type to existing generators."""
from typing import Optional
from db.database import AsyncSessionLocal
from db.models import GeneratedOutput

SUPPORTED_TYPES = {
    "audit_report", "profit_loss", "balance_sheet", "cash_flow",
    "tax_schedule", "management_report", "custom",
}


async def enqueue(profile_id: str, output_type: str, template_id: Optional[str]) -> str:
    if output_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported output_type: {output_type}")
    async with AsyncSessionLocal() as s:
        row = GeneratedOutput(
            profile_id=profile_id,
            output_type=output_type,
            template_id=template_id,
            status="pending",
        )
        s.add(row)
        await s.commit()
        job_id = row.id
    await _schedule(job_id)
    return job_id


async def _schedule(job_id: str) -> None:
    """Run the background generation task. Patched in tests."""
    import asyncio
    asyncio.create_task(_run(job_id))


async def _run(job_id: str) -> None:
    """Runs the actual generation."""
    async with AsyncSessionLocal() as s:
        row = await s.get(GeneratedOutput, job_id)
        if row is None:
            return
        row.status = "processing"
        await s.commit()
    try:
        output_path = await _dispatch(job_id)
        async with AsyncSessionLocal() as s:
            row = await s.get(GeneratedOutput, job_id)
            row.status = "ready"
            row.output_path = output_path
            await s.commit()
    except Exception as e:  # noqa: BLE001
        async with AsyncSessionLocal() as s:
            row = await s.get(GeneratedOutput, job_id)
            row.status = "failed"
            row.error_message = str(e)
            await s.commit()


async def _dispatch(job_id: str) -> str:
    """Route to the appropriate generator. Returns file path."""
    async with AsyncSessionLocal() as s:
        row = await s.get(GeneratedOutput, job_id)
    return await _generate_by_type(row.profile_id, row.output_type, row.template_id, job_id)


async def _generate_by_type(profile_id: str, output_type: str, template_id, job_id: str) -> str:
    """Load profile + trial balance from DB, call generate_audit_report, write PDF."""
    import json as _json
    from pathlib import Path
    from sqlalchemy import select
    from db.models import AuditProfile, ProfileVersion, SourceDocument
    from core.structured_report_generator import generate_audit_report

    out_dir = Path("storage/generated")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load AuditProfile, current ProfileVersion, and SourceDocuments
    async with AsyncSessionLocal() as s:
        audit_profile = await s.get(AuditProfile, profile_id)

        pv_result = await s.execute(
            select(ProfileVersion)
            .where(ProfileVersion.profile_id == profile_id, ProfileVersion.is_current.is_(True))
            .limit(1)
        )
        profile_version = pv_result.scalar_one_or_none()

        sd_result = await s.execute(
            select(SourceDocument).where(
                SourceDocument.profile_id == profile_id,
                SourceDocument.status != "error",
            )
        )
        source_docs = sd_result.scalars().all()

    # 2. Parse profile_json (Text column — may be None, str, or already dict)
    raw_pj = profile_version.profile_json if profile_version else None
    if raw_pj is None:
        profile_dict: dict = {}
    elif isinstance(raw_pj, dict):
        profile_dict = raw_pj
    else:
        try:
            profile_dict = _json.loads(raw_pj)
        except (ValueError, TypeError):
            profile_dict = {}

    # 3. Extract trial balance rows from the matching SourceDocument
    tb_doc = next((d for d in source_docs if d.document_type == "trial_balance"), None)
    tb_data: list = []
    if tb_doc and tb_doc.extracted_data:
        ed = tb_doc.extracted_data
        if isinstance(ed, list):
            tb_data = ed
        elif isinstance(ed, dict):
            tb_data = ed.get("rows", ed.get("trial_balance", []))

    # 4. Build company_info from AuditProfile
    company_info = {
        "company_name": (audit_profile.client_name if audit_profile else None) or "",
        "period_end": (audit_profile.period_end if audit_profile else None) or "",
        "profile_id": profile_id,
    }

    # 5. Generate the structured report
    report_data = generate_audit_report(
        trial_balance=tb_data,
        profile=profile_dict,
        company_info=company_info,
    )

    # 6. Write PDF; fall back to JSON if PDF generation fails
    out_path = out_dir / f"{job_id}.pdf"
    try:
        _write_report_pdf(report_data, out_path)
    except Exception:  # noqa: BLE001
        out_path = out_dir / f"{job_id}.json"
        out_path.write_text(_json.dumps(report_data, indent=2, default=str), encoding="utf-8")

    return str(out_path)


def _write_report_pdf(report_data: dict, out_path) -> None:
    """Render report_data dict to a ReportLab PDF at out_path."""
    import json as _json
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4

    doc = SimpleDocTemplate(str(out_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    meta = report_data.get("metadata", {})
    title = f"Audit Report: {meta.get('company_name', 'Unknown')}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 12))

    for section_key, section_val in report_data.items():
        story.append(Paragraph(section_key.replace("_", " ").title(), styles["Heading2"]))
        story.append(Paragraph(
            _json.dumps(section_val, indent=2, default=str)[:2000].replace("\n", "<br/>"),
            styles["Code"],
        ))
        story.append(Spacer(1, 8))

    doc.build(story)
