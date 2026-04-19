"""
FastAPI routes for Template Learning System.
Provides upload, learn, list, get, delete, and publish endpoints.
"""
import copy
import json
import os
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from core.template_analyzer import TemplateAnalyzer
from core.template_verifier import TemplateVerifier
from core.template_store import TemplateStore, _UNSET
from core.confidence_calibrator import ConfidenceCalibrator
from core.format_fingerprinter import FormatFingerprinter
from core.auto_verifier import AutoVerifier
from db.database import get_db
from db.models import Template

router = APIRouter(prefix="/api/templates", tags=["templates"])

_analyzer = TemplateAnalyzer()
_verifier = TemplateVerifier()
_calibrator = ConfidenceCalibrator()

# In-memory job tracking (adequate for single-process; replace with Redis at scale)
_jobs: dict = {}


async def _fast_learn_pipeline(
    pdf_path: str,
    name: str,
    user_id: Optional[str],
    db: AsyncSession,
) -> dict:
    """
    Fast-learn pipeline: fingerprint → (clone or analyze_precise) → verify → save.

    Returns the new fast-learn response schema:
      {template_id, status, confidence, time_taken_sec, match_source, hints}
    """
    start = time.time()

    fingerprinter = FormatFingerprinter()
    match_config, match_score, match_source = await run_in_threadpool(fingerprinter.match, pdf_path)

    if match_score >= 88 and match_config is not None:
        config = copy.deepcopy(match_config)
    else:
        analyzer = TemplateAnalyzer()
        config = await run_in_threadpool(analyzer.analyze_precise, pdf_path)

    verifier = AutoVerifier()
    verify_result = await run_in_threadpool(verifier.verify, config, pdf_path)

    calibrated_confidence = _calibrator.calibrate(verify_result["confidence"], [])

    store = TemplateStore(db)
    tmpl = await store.save(
        name=name,
        config=config,
        user_id=user_id,
        status=verify_result["status"],
        confidence_score=calibrated_confidence,
        source_pdf_name=os.path.basename(pdf_path),
        page_count=config.get("page_count"),
    )

    try:
        os.remove(pdf_path)
    except OSError:
        pass

    return {
        "template_id": tmpl.id,
        "status": verify_result["status"],
        "confidence": round(calibrated_confidence, 4),
        "time_taken_sec": round(time.time() - start, 1),
        "match_source": match_source or "none",
        "hints": verify_result.get("hints"),
    }


@router.post("/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    name: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    fast_learn: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload a reference PDF to learn its format.

    fast_learn=false (default): saves the PDF and returns a job_id for async processing.
    fast_learn=true: runs the full fast-learn pipeline synchronously and returns
                     {template_id, status, confidence, time_taken_sec, match_source, hints}.
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

    if fast_learn:
        return await _fast_learn_pipeline(temp_path, template_name, user_id, db)

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
        from db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_session:
            store = TemplateStore(bg_session)
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
                await bg_session.commit()

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
                await bg_session.rollback()
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


@router.get("/prebuilt")
async def list_prebuilt_formats(
    format_family: Optional[str] = Query(default=None),
) -> dict:
    """List pre-built format templates shipped with the app."""
    from core.prebuilt_formats import PREBUILT_FORMATS, get_prebuilt_by_family

    if format_family:
        formats = get_prebuilt_by_family(format_family)
    else:
        formats = PREBUILT_FORMATS

    return {
        "formats": [
            {
                "id": f["id"],
                "name": f["name"],
                "format_family": f["format_family"],
                "format_variant": f["format_variant"],
                "description": f["description"],
            }
            for f in formats
        ]
    }


@router.post("/prebuilt/{format_id}/apply")
async def apply_prebuilt_format(
    format_id: str,
    user_id: str = Query(...),
    name: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Apply (save) a pre-built format as a user's template.
    Creates a DB template entry from the prebuilt config.
    """
    from core.prebuilt_formats import get_prebuilt_by_id

    prebuilt = get_prebuilt_by_id(format_id)
    if not prebuilt:
        raise HTTPException(status_code=404, detail="Pre-built format not found")

    store = TemplateStore(db)
    template_name = name or prebuilt["name"]

    existing = await store.list_user_templates(user_id, format_family=prebuilt["format_family"])
    matching = [t for t in existing if t.name == template_name]
    if matching:
        t = matching[0]
        return {
            "message": f"Pre-built format '{prebuilt['name']}' already applied",
            "template_id": t.id,
            "name": t.name,
            "format_family": t.format_family,
            "format_variant": t.format_variant,
        }

    synthetic_report = json.dumps({
        "overall_passed": True,
        "confidence": 1.0,
        "source": "prebuilt",
        "checks": []
    })

    tmpl = await store.save(
        name=template_name,
        config=prebuilt["config"],
        user_id=user_id,
        status="verified",
        confidence_score=1.0,
        verification_report=synthetic_report,
        format_family=prebuilt["format_family"],
        format_variant=prebuilt["format_variant"],
    )

    return {
        "message": f"Pre-built format '{prebuilt['name']}' applied as template",
        "template_id": tmpl.id,
        "name": tmpl.name,
        "format_family": tmpl.format_family,
        "format_variant": tmpl.format_variant,
    }


@router.post("/retrain")
async def retrain_all_templates(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrain confidence scores for ALL templates using accumulated feedback."""
    from sqlalchemy import select as sa_select
    from db.models import TemplateFeedback
    from sqlalchemy import update as sa_update

    tmpl_result = await db.execute(sa_select(Template))
    templates = tmpl_result.scalars().all()

    results = []
    for tmpl in templates:
        fb_result = await db.execute(
            sa_select(TemplateFeedback).where(TemplateFeedback.template_id == tmpl.id)
        )
        feedbacks = fb_result.scalars().all()
        if not feedbacks:
            results.append({
                "template_id": tmpl.id,
                "name": tmpl.name,
                "action": "skipped",
                "reason": "no_feedback",
            })
            continue

        history = [
            {"feedback_type": f.feedback_type, "original_confidence": tmpl.confidence_score}
            for f in feedbacks
        ]
        old_score = tmpl.confidence_score
        new_score = _calibrator.calibrate(old_score, history)

        if tmpl.is_global and new_score < 0.5:
            new_score = max(new_score, 0.5)

        await db.execute(
            sa_update(Template).where(Template.id == tmpl.id).values(confidence_score=new_score)
        )
        results.append({
            "template_id": tmpl.id,
            "name": tmpl.name,
            "action": "retrained",
            "old_confidence": round(old_score, 4),
            "new_confidence": round(new_score, 4),
        })

    await db.commit()
    return {
        "retrained": len([r for r in results if r["action"] == "retrained"]),
        "results": results,
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
        from db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_session:
            store = TemplateStore(bg_session)
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
                await bg_session.commit()

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
                await bg_session.rollback()
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
    # Normalize aliases: "accurate"→"correct", "inaccurate"→"incorrect"
    _type_aliases = {"accurate": "correct", "inaccurate": "incorrect"}
    feedback_type = _type_aliases.get(feedback_type, feedback_type)
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


@router.get("/{template_id}/confidence-history")
async def get_confidence_history(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return feedback history and calibration summary for a template."""
    from sqlalchemy import select as sa_select
    from db.models import TemplateFeedback

    template = await db.get(Template, template_id)
    if not template:
        raise HTTPException(404, f"Template {template_id} not found")

    result = await db.execute(
        sa_select(TemplateFeedback)
        .where(TemplateFeedback.template_id == template_id)
        .order_by(TemplateFeedback.created_at)
    )
    feedback_rows = result.scalars().all()

    history = [
        {
            "id": f.id,
            "feedback_type": f.feedback_type,
            "original_confidence": template.confidence_score,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in feedback_rows
    ]

    summary = _calibrator.get_calibration_summary(history)

    return {
        "template_id": template_id,
        "current_confidence": template.confidence_score,
        "feedback_count": len(history),
        "history": history,
        "calibration_summary": summary,
    }


@router.post("/{template_id}/retrain")
async def retrain_single_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrain confidence score for a single template using its feedback."""
    from sqlalchemy import select as sa_select
    from db.models import TemplateFeedback
    from sqlalchemy import update as sa_update

    template = await db.get(Template, template_id)
    if not template:
        raise HTTPException(404, f"Template {template_id} not found")

    fb_result = await db.execute(
        sa_select(TemplateFeedback).where(TemplateFeedback.template_id == template_id)
    )
    feedbacks = fb_result.scalars().all()

    if not feedbacks:
        return {
            "template_id": template_id,
            "action": "skipped",
            "reason": "no_feedback",
            "current_confidence": template.confidence_score,
        }

    history = [
        {"feedback_type": f.feedback_type, "original_confidence": template.confidence_score}
        for f in feedbacks
    ]
    old_score = template.confidence_score
    new_score = _calibrator.calibrate(old_score, history)

    if template.is_global and new_score < 0.5:
        new_score = max(new_score, 0.5)

    await db.execute(
        sa_update(Template).where(Template.id == template_id).values(confidence_score=new_score)
    )
    await db.commit()

    summary = _calibrator.get_calibration_summary(history)
    return {
        "template_id": template_id,
        "action": "retrained",
        "old_confidence": round(old_score, 4),
        "new_confidence": round(new_score, 4),
        "calibration_summary": summary,
    }


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
