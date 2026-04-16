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
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import AuditProfile, SourceDocument
from core.document_analyzer import analyze_document
from core.audit_profile_builder import build_profile_from_documents
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
