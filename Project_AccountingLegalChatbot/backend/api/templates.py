"""
FastAPI routes for Template Learning System.
Provides upload, learn, list, get, delete, and publish endpoints.
"""
import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.template_analyzer import TemplateAnalyzer
from core.template_verifier import TemplateVerifier
from core.template_store import TemplateStore, _UNSET
from db.database import get_db

router = APIRouter(prefix="/api/templates", tags=["templates"])

_analyzer = TemplateAnalyzer()
_verifier = TemplateVerifier()

# In-memory job tracking (adequate for single-process; replace with Redis at scale)
_jobs: dict = {}


@router.post("/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    name: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
) -> dict:
    """
    Upload a reference PDF to learn its format.
    Saves the PDF and returns a job_id for tracking progress.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    job_id = str(uuid.uuid4())
    template_name = name or (file.filename or "").replace(".pdf", "") or f"template-{job_id[:8]}"

    temp_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "temp_templates")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{job_id}_{file.filename}")

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    _jobs[job_id] = {
        "status": "pending",
        "template_name": template_name,
        "user_id": user_id,
        "pdf_path": temp_path,
        "progress": 0,
    }

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Reference PDF uploaded. Call POST /api/templates/learn/{job_id} to start analysis.",
    }


@router.post("/learn/{job_id}")
async def start_learning(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Start background template learning for an uploaded PDF.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    if job["status"] not in ("pending", "failed"):
        return {"job_id": job_id, "status": job["status"], "message": "Job already running or complete"}

    _jobs[job_id]["status"] = "processing"

    async def _learn():
        store = TemplateStore(db)
        try:
            _jobs[job_id]["progress"] = 20
            config = _analyzer.analyze(_jobs[job_id]["pdf_path"])
            _jobs[job_id]["progress"] = 60

            report = _verifier.generate_report(config)
            _jobs[job_id]["progress"] = 80

            status = "verified" if report["overall_passed"] else "needs_review"

            tmpl = await store.save(
                name=_jobs[job_id]["template_name"],
                config=config,
                user_id=_jobs[job_id]["user_id"],
                status=status,
                confidence_score=report["confidence"],
                verification_report=json.dumps(report),
                page_count=config.get("page_count"),
                source_pdf_name=config.get("source"),
            )

            _jobs[job_id].update({
                "status": status,
                "template_id": tmpl.id,
                "confidence": report["confidence"],
                "progress": 100,
            })

            # Clean up temp file
            try:
                os.remove(_jobs[job_id]["pdf_path"])
            except OSError:
                pass

        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["progress"] = 100

    background_tasks.add_task(_learn)

    return {"job_id": job_id, "status": "processing", "message": "Template learning started"}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Get the current status of a learning job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "template_id": job.get("template_id"),
        "confidence": job.get("confidence"),
        "error": job.get("error"),
    }


@router.get("/list")
async def list_templates(
    user_id: str = Query(...),
    status: Optional[str] = Query(default=None),
    format_family: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all templates for a user."""
    store = TemplateStore(db)
    templates = await store.list_user_templates(user_id, status=status, format_family=format_family)
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "confidence": t.confidence_score,
                "source_pdf_name": t.source_pdf_name,
                "page_count": t.page_count,
                "is_global": t.is_global,
                "format_family": t.format_family,
                "format_variant": t.format_variant,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ]
    }


@router.get("/library")
async def list_global_templates(
    format_family: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List globally shared templates."""
    store = TemplateStore(db)
    templates = await store.list_global_templates(format_family=format_family)
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "confidence": t.confidence_score,
                "source_pdf_name": t.source_pdf_name,
                "format_family": t.format_family,
                "format_variant": t.format_variant,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ]
    }


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full template config by ID."""
    store = TemplateStore(db)
    tmpl = await store.load(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "status": tmpl.status,
        "confidence": tmpl.confidence_score,
        "config": store.get_config(tmpl),
        "verification_report": json.loads(tmpl.verification_report) if tmpl.verification_report else None,
        "source_pdf_name": tmpl.source_pdf_name,
        "page_count": tmpl.page_count,
        "is_global": tmpl.is_global,
        "format_family": tmpl.format_family,
        "format_variant": tmpl.format_variant,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
    }


@router.post("/publish/{template_id}")
async def publish_to_library(
    template_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a verified template to the global library."""
    store = TemplateStore(db)
    tmpl = await store.load(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized: not the template owner")
    if tmpl.status not in ("verified", "ready"):
        raise HTTPException(
            status_code=400,
            detail=f"Template status '{tmpl.status}' cannot be published; must be verified or ready",
        )

    await store.publish_global(template_id)
    return {"message": "Template published to global library", "template_id": template_id}


@router.put("/{template_id}")
async def update_template_config(
    template_id: str,
    payload: dict,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update template config (manual fine-tuning)."""
    store = TemplateStore(db)
    tmpl = await store.load(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.user_id and tmpl.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    new_config = payload.get("config")
    if not new_config:
        raise HTTPException(status_code=400, detail="config field required")

    new_name = payload.get("name", tmpl.name)
    new_format_family = payload.get("format_family")
    # Distinguish "key absent" (don't touch) from "key present and null" (clear)
    new_format_variant = payload["format_variant"] if "format_variant" in payload else _UNSET

    report = _verifier.generate_report(new_config)
    new_status = "verified" if report["overall_passed"] else "needs_review"

    await store.update_config(
        template_id=template_id,
        config=new_config,
        name=new_name,
        status=new_status,
        confidence_score=report["confidence"],
        verification_report=json.dumps(report),
        format_family=new_format_family,
        format_variant=new_format_variant,
    )

    return {
        "message": "Template updated",
        "template_id": template_id,
        "status": new_status,
        "confidence": report["confidence"],
    }


@router.post("/batch-learn")
async def batch_learn(
    files: List[UploadFile] = File(...),
    name: str = Query(...),
    user_id: Optional[str] = Query(default=None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload multiple reference PDFs and produce a consensus template config.
    Returns job_id for polling.
    """
    from core.batch_template_learner import BatchTemplateLearner

    if len(files) < 1:
        raise HTTPException(status_code=400, detail="At least one PDF required")

    job_id = str(uuid.uuid4())
    temp_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "temp_templates")
    os.makedirs(temp_dir, exist_ok=True)

    pdf_paths = []
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{f.filename} is not a PDF")
        temp_path = os.path.join(temp_dir, f"{job_id}_{f.filename}")
        content = await f.read()
        with open(temp_path, "wb") as fp:
            fp.write(content)
        pdf_paths.append(temp_path)

    _jobs[job_id] = {
        "status": "processing",
        "template_name": name,
        "user_id": user_id,
        "pdf_paths": pdf_paths,
        "progress": 0,
        "pdf_count": len(files),
    }

    async def _batch_learn_task():
        store = TemplateStore(db)
        try:
            _jobs[job_id]["progress"] = 20
            learner = BatchTemplateLearner()
            config = learner.learn_from_multiple(pdf_paths)
            _jobs[job_id]["progress"] = 70

            report = _verifier.generate_report(config)
            _jobs[job_id]["progress"] = 85

            status = "verified" if report["overall_passed"] else "needs_review"

            tmpl = await store.save(
                name=name,
                config=config,
                user_id=user_id,
                status=status,
                confidence_score=report["confidence"],
                verification_report=json.dumps(report),
                page_count=config.get("page_count"),
                source_pdf_name=config.get("source"),
            )

            _jobs[job_id].update({
                "status": status,
                "template_id": tmpl.id,
                "confidence": report["confidence"],
                "progress": 100,
            })

            for p in pdf_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass

        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["progress"] = 100

    background_tasks.add_task(_batch_learn_task)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"Batch learning started for {len(files)} PDF(s)",
        "pdf_count": len(files),
    }


@router.post("/{template_id}/feedback")
async def submit_feedback(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit user feedback on template accuracy.
    Recomputes confidence_score based on feedback history.

    Payload: {
        "user_id": str (optional),
        "feedback_type": "correct" | "incorrect" | "partial",
        "element": "page" | "margins" | "fonts" | "tables" | "sections" (optional),
        "correction_json": dict (optional, the corrected value),
        "notes": str (optional)
    }
    """
    feedback_type = payload.get("feedback_type")
    if feedback_type not in ("correct", "incorrect", "partial"):
        raise HTTPException(
            status_code=400,
            detail="feedback_type must be 'correct', 'incorrect', or 'partial'",
        )

    store = TemplateStore(db)
    tmpl = await store.load(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    result = await store.submit_feedback(
        template_id=template_id,
        feedback_type=feedback_type,
        user_id=payload.get("user_id"),
        element=payload.get("element"),
        correction_json=payload.get("correction_json"),
        notes=payload.get("notes"),
    )

    return result


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a template (owner only)."""
    store = TemplateStore(db)
    tmpl = await store.load(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized: not the template owner")

    await store.delete(template_id)
    return {"message": "Template deleted", "template_id": template_id}
