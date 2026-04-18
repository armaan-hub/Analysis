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
    """
    Dispatch to generators. Today each branch writes a minimal placeholder PDF.
    Replace with real calls to core.report_generator.* as integration is proven.
    """
    from pathlib import Path
    out_dir = Path("storage/generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_id}.pdf"

    out_path.write_bytes(b"%PDF-1.4 placeholder")
    return str(out_path)
