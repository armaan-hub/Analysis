"""
Audit Profiles API — Create/manage audit profiles and upload source documents.

Part of the NotebookLM-style document understanding system.
Profiles learn from uploaded documents to generate perfectly formatted audit reports.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import AuditProfile, SourceDocument
from core.document_analyzer import analyze_document
from core.audit_profile_builder import build_profile_from_documents
from core.structured_report_generator import generate_audit_report
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit-profiles", tags=["Audit Profiles"])

# Upload directory for profile source documents
PROFILE_UPLOAD_DIR = Path(settings.upload_dir) / "audit_profiles"


# ── Request / Response Schemas ────────────────────────────────────

class CreateProfileRequest(BaseModel):
    engagement_name: str
    client_name: Optional[str] = ""
    period_end: Optional[str] = ""


class UpdateProfileRequest(BaseModel):
    engagement_name: Optional[str] = None
    client_name: Optional[str] = None
    period_end: Optional[str] = None
    profile_json: Optional[dict] = None


class ProfileResponse(BaseModel):
    id: str
    engagement_name: str
    client_name: Optional[str]
    period_end: Optional[str]
    status: str
    profile_json: Optional[dict]
    source_files: Optional[list]
    created_at: str
    updated_at: str


class SourceDocumentResponse(BaseModel):
    id: str
    document_type: str
    original_filename: str
    confidence: float
    status: str
    extracted_data: Optional[dict]
    uploaded_at: str


# ── Helpers ───────────────────────────────────────────────────────

def _profile_to_response(p: AuditProfile) -> dict:
    return {
        "id": p.id,
        "engagement_name": p.engagement_name,
        "client_name": p.client_name or "",
        "period_end": p.period_end or "",
        "status": p.status,
        "profile_json": p.profile_json,
        "source_files": p.source_files or [],
        "created_at": str(p.created_at),
        "updated_at": str(p.updated_at),
    }


def _source_doc_to_response(d: SourceDocument) -> dict:
    return {
        "id": d.id,
        "document_type": d.document_type,
        "original_filename": d.original_filename,
        "confidence": d.confidence,
        "status": d.status,
        "extracted_data": d.extracted_data,
        "uploaded_at": str(d.uploaded_at),
    }


# ═══════════════════════════════════════════════════════════════════
# Profile CRUD
# ═══════════════════════════════════════════════════════════════════

@router.post("", status_code=201)
async def create_profile(req: CreateProfileRequest, db: AsyncSession = Depends(get_db)):
    """Create a new audit profile (engagement)."""
    profile = AuditProfile(
        engagement_name=req.engagement_name,
        client_name=req.client_name,
        period_end=req.period_end,
        profile_json={},
        source_files=[],
        status="draft",
    )
    db.add(profile)
    await db.flush()
    logger.info(f"Created audit profile {profile.id}: {req.engagement_name}")
    return _profile_to_response(profile)


@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """List all audit profiles."""
    result = await db.execute(
        select(AuditProfile).order_by(desc(AuditProfile.created_at))
    )
    profiles = result.scalars().all()
    return [_profile_to_response(p) for p in profiles]


@router.get("/{profile_id}")
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific audit profile."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")
    return _profile_to_response(profile)


@router.put("/{profile_id}")
async def update_profile(
    profile_id: str, req: UpdateProfileRequest, db: AsyncSession = Depends(get_db)
):
    """Update profile metadata or learned profile_json."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    if req.engagement_name is not None:
        profile.engagement_name = req.engagement_name
    if req.client_name is not None:
        profile.client_name = req.client_name
    if req.period_end is not None:
        profile.period_end = req.period_end
    if req.profile_json is not None:
        profile.profile_json = req.profile_json

    await db.flush()
    logger.info(f"Updated audit profile {profile_id}")
    return _profile_to_response(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an audit profile and all its source documents."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")
    await db.delete(profile)
    await db.flush()
    logger.info(f"Deleted audit profile {profile_id}")


# ═══════════════════════════════════════════════════════════════════
# Source Document Upload
# ═══════════════════════════════════════════════════════════════════

@router.post("/{profile_id}/upload-source")
async def upload_source_document(
    profile_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a source document to an audit profile.
    Automatically extracts structured data (tables, text, structure).
    
    document_type: trial_balance | prior_audit | template | chart_of_accounts | custom
    """
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    valid_types = {"trial_balance", "prior_audit", "template", "chart_of_accounts", "custom"}
    if document_type not in valid_types:
        raise HTTPException(400, f"Invalid document_type. Must be one of: {valid_types}")

    # Save file to disk
    profile_dir = PROFILE_UPLOAD_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = profile_dir / safe_name

    content = await file.read()
    file_path.write_bytes(content)
    logger.info(f"Saved source document: {file_path} ({len(content)} bytes)")

    # Create DB record (processing state)
    source_doc = SourceDocument(
        profile_id=profile_id,
        document_type=document_type,
        original_filename=file.filename or "unknown",
        file_path=str(file_path),
        status="processing",
    )
    db.add(source_doc)
    await db.flush()

    # Run extraction
    try:
        extraction = analyze_document(str(file_path))
        table_count = len(extraction.get("tables", []))
        text_len = len(extraction.get("text", ""))

        # Compute confidence based on extraction richness
        confidence = 0.0
        if table_count > 0:
            confidence += 0.4
        if text_len > 500:
            confidence += 0.3
        if extraction.get("structure", {}).get("headings"):
            confidence += 0.2
        if extraction.get("error"):
            confidence = max(confidence - 0.3, 0.0)
        else:
            confidence += 0.1
        confidence = min(confidence, 1.0)

        source_doc.extracted_data = extraction
        source_doc.confidence = round(confidence, 2)
        source_doc.status = "extracted"

        # Update profile source_files metadata
        files_meta = profile.source_files or []
        files_meta.append({
            "document_id": source_doc.id,
            "filename": file.filename,
            "type": document_type,
            "confidence": source_doc.confidence,
            "tables": table_count,
        })
        profile.source_files = files_meta

        await db.flush()
        logger.info(
            f"Extraction complete for {file.filename}: "
            f"{table_count} tables, {text_len} chars text, confidence={confidence:.0%}"
        )

    except Exception as e:
        source_doc.status = "error"
        source_doc.error_message = str(e)
        await db.flush()
        logger.error(f"Extraction failed for {file.filename}: {e}")

    return _source_doc_to_response(source_doc)


@router.get("/{profile_id}/source-documents")
async def list_source_documents(profile_id: str, db: AsyncSession = Depends(get_db)):
    """List all source documents for a profile."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    result = await db.execute(
        select(SourceDocument)
        .where(SourceDocument.profile_id == profile_id)
        .order_by(SourceDocument.uploaded_at)
    )
    docs = result.scalars().all()
    return [_source_doc_to_response(d) for d in docs]


# ═══════════════════════════════════════════════════════════════════
# Profile Building (merge all source extractions into profile)
# ═══════════════════════════════════════════════════════════════════

@router.post("/{profile_id}/build-profile")
async def build_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """
    Trigger profile building: merge all uploaded source document extractions
    into a unified audit_profile JSON.
    """
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    # Fetch all extracted source documents
    result = await db.execute(
        select(SourceDocument)
        .where(SourceDocument.profile_id == profile_id)
        .where(SourceDocument.status == "extracted")
    )
    source_docs = result.scalars().all()

    if not source_docs:
        raise HTTPException(400, "No extracted source documents found. Upload documents first.")

    # Collect extraction dicts
    extractions = []
    for doc in source_docs:
        if doc.extracted_data:
            extractions.append(doc.extracted_data)

    # Build unified profile
    try:
        profile.status = "learning"
        await db.flush()

        built_profile = build_profile_from_documents(
            documents=extractions,
            client_name=profile.client_name or "",
            period_end=profile.period_end or "",
        )

        profile.profile_json = built_profile
        profile.status = "ready"
        await db.flush()

        logger.info(
            f"Profile {profile_id} built: "
            f"{len(built_profile.get('account_mapping', {}))} account mappings, "
            f"{len(built_profile.get('source_summary', []))} sources"
        )

    except Exception as e:
        profile.status = "draft"
        await db.flush()
        logger.error(f"Profile building failed for {profile_id}: {e}")
        raise HTTPException(500, f"Profile building failed: {str(e)}")

    return _profile_to_response(profile)


# ═══════════════════════════════════════════════════════════════════
# Account Mapping Management
# ═══════════════════════════════════════════════════════════════════

@router.get("/{profile_id}/account-mapping")
async def get_account_mapping(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Get the account mapping section of the profile."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    pj = profile.profile_json or {}
    return {
        "profile_id": profile_id,
        "account_mapping": pj.get("account_mapping", {}),
        "total_accounts": len(pj.get("account_mapping", {})),
    }


class UpdateMappingRequest(BaseModel):
    account_name: str
    mapped_to: str


@router.put("/{profile_id}/account-mapping")
async def update_account_mapping(
    profile_id: str,
    req: UpdateMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a single account mapping in the profile."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    pj = dict(profile.profile_json or {})
    mappings = dict(pj.get("account_mapping", {}))

    mappings[req.account_name] = {
        "name": req.account_name,
        "mapped_to": req.mapped_to,
        "confidence": 1.0,
        "source": "user_override",
    }

    pj["account_mapping"] = mappings
    profile.profile_json = pj
    await db.flush()

    logger.info(f"Updated mapping: {req.account_name} → {req.mapped_to}")
    return {
        "profile_id": profile_id,
        "account_name": req.account_name,
        "mapped_to": req.mapped_to,
        "total_accounts": len(mappings),
    }


class BulkMappingRequest(BaseModel):
    mappings: dict  # {account_name: mapped_to_group}


@router.put("/{profile_id}/account-mapping/bulk")
async def bulk_update_account_mapping(
    profile_id: str,
    req: BulkMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk update account mappings."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    pj = dict(profile.profile_json or {})
    mappings = dict(pj.get("account_mapping", {}))

    for account_name, mapped_to in req.mappings.items():
        mappings[account_name] = {
            "name": account_name,
            "mapped_to": mapped_to,
            "confidence": 1.0,
            "source": "user_override",
        }

    pj["account_mapping"] = mappings
    profile.profile_json = pj
    await db.flush()

    logger.info(f"Bulk updated {len(req.mappings)} account mappings for profile {profile_id}")
    return {
        "profile_id": profile_id,
        "updated_count": len(req.mappings),
        "total_accounts": len(mappings),
    }


# ═══════════════════════════════════════════════════════════════════
# Format Template Management
# ═══════════════════════════════════════════════════════════════════

@router.get("/{profile_id}/format-template")
async def get_format_template(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Get the format template section of the profile."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    pj = profile.profile_json or {}
    return {
        "profile_id": profile_id,
        "format_template": pj.get("format_template", {}),
        "custom_requirements": pj.get("custom_requirements", {}),
    }


class UpdateFormatRequest(BaseModel):
    format_template: Optional[dict] = None
    custom_requirements: Optional[dict] = None


@router.put("/{profile_id}/format-template")
async def update_format_template(
    profile_id: str,
    req: UpdateFormatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update format template and/or custom requirements."""
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    pj = dict(profile.profile_json or {})

    if req.format_template is not None:
        pj["format_template"] = req.format_template
    if req.custom_requirements is not None:
        pj["custom_requirements"] = req.custom_requirements

    profile.profile_json = pj
    await db.flush()

    logger.info(f"Updated format template for profile {profile_id}")
    return {
        "profile_id": profile_id,
        "format_template": pj.get("format_template", {}),
        "custom_requirements": pj.get("custom_requirements", {}),
    }


# ═══════════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════════

@router.post("/{profile_id}/generate-report")
async def generate_report_endpoint(
    profile_id: str,
    file: UploadFile = File(...),
    company_name: Optional[str] = Form(None),
    period_end: Optional[str] = Form(None),
    auditor_name: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a structured audit report from trial balance + profile.
    Uploads a trial balance file (Excel/PDF), uses the profile's learned
    mappings and format template, returns a complete audit_report.json.
    """
    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    if not profile.profile_json or not profile.profile_json.get("account_mapping"):
        raise HTTPException(400, "Profile has no learned data. Build the profile first.")

    # Save uploaded trial balance
    profile_dir = PROFILE_UPLOAD_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"tb_{uuid.uuid4().hex[:8]}_{file.filename}"
    tb_path = profile_dir / safe_name
    content = await file.read()
    tb_path.write_bytes(content)

    # Extract trial balance data
    extraction = analyze_document(str(tb_path))
    tables = extraction.get("tables", [])
    if not tables:
        raise HTTPException(400, "No data tables found in the uploaded file.")

    # Convert table to list of dicts (first row = header)
    tb_rows = _table_to_dicts(tables[0])
    if not tb_rows:
        raise HTTPException(400, "Could not parse trial balance data from file.")

    # Build company_info
    company_info = {
        "profile_id": profile_id,
        "company_name": company_name or profile.client_name or "",
        "period_end": period_end or profile.period_end or "",
        "auditor_name": auditor_name or "",
        "currency": currency or profile.profile_json.get("custom_requirements", {}).get("currency", "AED"),
    }

    try:
        report_json = generate_audit_report(
            trial_balance=tb_rows,
            profile=profile.profile_json,
            company_info=company_info,
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(500, f"Report generation failed: {str(e)}")

    logger.info(
        f"Generated report for profile {profile_id}: "
        f"{len(tb_rows)} TB rows processed"
    )
    return {"profile_id": profile_id, "report": report_json, "tb_rows_processed": len(tb_rows)}


def _table_to_dicts(table: list[list[str]]) -> list[dict]:
    """Convert a 2D table (first row = headers) to list of dicts."""
    if len(table) < 2:
        return []
    headers = [str(h).strip() for h in table[0]]
    rows = []
    for row in table[1:]:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        d = {h: padded[i] for i, h in enumerate(headers) if h}
        if any(str(v).strip() for v in d.values()):
            rows.append(d)
    return rows


# ═══════════════════════════════════════════════════════════════════
# Report Export (PDF / DOCX / Excel)
# ═══════════════════════════════════════════════════════════════════

EXPORT_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("/{profile_id}/export-report/{fmt}")
async def export_report(
    profile_id: str,
    fmt: str,
    file: UploadFile = File(...),
    company_name: Optional[str] = Form(None),
    period_end: Optional[str] = Form(None),
    auditor_name: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and export an audit report in the specified format.
    Accepts a trial balance file, generates the report, converts to PDF/DOCX/XLSX.
    """
    if fmt not in EXPORT_MIME:
        raise HTTPException(400, f"Unsupported format '{fmt}'. Use: pdf, docx, xlsx")

    profile = await db.get(AuditProfile, profile_id)
    if not profile:
        raise HTTPException(404, f"Profile {profile_id} not found")

    if not profile.profile_json or not profile.profile_json.get("account_mapping"):
        raise HTTPException(400, "Profile has no learned data. Build the profile first.")

    # Save uploaded trial balance
    profile_dir = PROFILE_UPLOAD_DIR / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"export_{uuid.uuid4().hex[:8]}_{file.filename}"
    tb_path = profile_dir / safe_name
    content = await file.read()
    tb_path.write_bytes(content)

    # Extract and parse trial balance
    extraction = analyze_document(str(tb_path))
    tables = extraction.get("tables", [])
    if not tables:
        raise HTTPException(400, "No data tables found in the uploaded file.")
    tb_rows = _table_to_dicts(tables[0])
    if not tb_rows:
        raise HTTPException(400, "Could not parse trial balance data from file.")

    company_info = {
        "profile_id": profile_id,
        "company_name": company_name or profile.client_name or "",
        "period_end": period_end or profile.period_end or "",
        "auditor_name": auditor_name or "",
        "currency": currency or profile.profile_json.get("custom_requirements", {}).get("currency", "AED"),
    }

    try:
        report_json = generate_audit_report(
            trial_balance=tb_rows, profile=profile.profile_json, company_info=company_info,
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(500, f"Report generation failed: {str(e)}")

    # Convert to requested format
    try:
        from core.format_applier import apply_format
        format_template = profile.profile_json.get("format_template")
        file_bytes = apply_format(report_json, format_template, fmt)
    except Exception as e:
        logger.error(f"Format export failed: {e}")
        raise HTTPException(500, f"Format export failed: {str(e)}")

    company = company_info.get("company_name", "report").replace(" ", "_")
    filename = f"audit_report_{company}.{fmt}"

    return Response(
        content=file_bytes,
        media_type=EXPORT_MIME[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
