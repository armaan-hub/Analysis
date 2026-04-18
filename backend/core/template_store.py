"""
Template CRUD operations using async SQLAlchemy.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Template, TemplateFeedback

# Sentinel used by update_config to distinguish "not provided" from explicit None.
_UNSET = object()


class TemplateStore:
    """Async SQLAlchemy-based template persistence layer."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        name: str,
        config: dict,
        user_id: Optional[str] = None,
        status: str = "draft",
        confidence_score: float = 0.0,
        verification_report: Optional[str] = None,
        page_count: Optional[int] = None,
        source_pdf_name: Optional[str] = None,
        template_id: Optional[str] = None,
        format_family: str = "custom",
        format_variant: Optional[str] = None,
    ) -> Template:
        """Create or replace a template."""
        config_json = json.dumps(config)
        now = datetime.now(timezone.utc)

        if template_id:
            # Update existing — only include format fields when explicitly supplied
            values = {
                "name": name,
                "config_json": config_json,
                "status": status,
                "confidence_score": confidence_score,
                "verification_report": verification_report,
                "page_count": page_count,
                "source_pdf_name": source_pdf_name,
                "updated_at": now,
            }
            if format_family != "custom":
                values["format_family"] = format_family
            if format_variant is not None:
                values["format_variant"] = format_variant
            await self.session.execute(
                update(Template)
                .where(Template.id == template_id)
                .values(**values)
            )
            await self.session.commit()
            return await self.load(template_id)
        else:
            tmpl = Template(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=name,
                config_json=config_json,
                status=status,
                confidence_score=confidence_score,
                verification_report=verification_report,
                page_count=page_count,
                source_pdf_name=source_pdf_name,
                format_family=format_family,
                format_variant=format_variant,
            )
            self.session.add(tmpl)
            await self.session.commit()
            await self.session.refresh(tmpl)
            return tmpl

    async def load(self, template_id: str) -> Optional[Template]:
        """Load a template by ID."""
        result = await self.session.execute(
            select(Template).where(Template.id == template_id)
        )
        return result.scalar_one_or_none()

    async def list_user_templates(
        self, user_id: str, status: Optional[str] = None, format_family: Optional[str] = None
    ) -> List[Template]:
        """List all templates for a user, optionally filtered by status and/or format_family."""
        q = select(Template).where(Template.user_id == user_id)
        if status:
            q = q.where(Template.status == status)
        if format_family:
            q = q.where(Template.format_family == format_family)
        q = q.order_by(Template.updated_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_global_templates(self, format_family: Optional[str] = None) -> List[Template]:
        """List globally shared templates, optionally filtered by format_family."""
        q = select(Template).where(Template.is_global == True)
        if format_family:
            q = q.where(Template.format_family == format_family)
        q = q.order_by(Template.updated_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def publish_global(self, template_id: str) -> Optional[Template]:
        """Mark a template as globally available."""
        await self.session.execute(
            update(Template)
            .where(Template.id == template_id)
            .values(is_global=True, updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        return await self.load(template_id)

    async def delete(self, template_id: str) -> bool:
        """Delete a template. Returns True if deleted."""
        tmpl = await self.load(template_id)
        if tmpl:
            await self.session.delete(tmpl)
            await self.session.commit()
            return True
        return False

    async def update_config(
        self,
        template_id: str,
        config: dict,
        name: str,
        status: str,
        confidence_score: float,
        verification_report: Optional[str] = None,
        format_family: Optional[str] = None,
        format_variant: object = _UNSET,
    ) -> None:
        """Update config, name, status, and confidence of an existing template."""
        values: dict = dict(
            config_json=json.dumps(config),
            name=name,
            status=status,
            confidence_score=confidence_score,
            verification_report=verification_report,
            updated_at=datetime.now(timezone.utc),
        )
        if format_family is not None:
            values["format_family"] = format_family
        if format_variant is not _UNSET:
            values["format_variant"] = format_variant  # includes None to clear
        stmt = (
            update(Template)
            .where(Template.id == template_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    def get_config(self, template: Template) -> dict:
        """Deserialize template config_json to dict."""
        return json.loads(template.config_json)

    async def submit_feedback(
        self,
        template_id: str,
        feedback_type: str,
        user_id: Optional[str] = None,
        element: Optional[str] = None,
        correction_json: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Save a feedback record and retune the template's confidence_score.

        Retuning formula:
          score_map = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
          - If total feedback count (including new) < 3: 70% current / 30% feedback avg
          - Otherwise: 40% current / 60% feedback avg
        Status update:
          - new_confidence >= 0.85  → "verified"
          - new_confidence < 0.85 and template is global or "ready" → "verified" (no demotion)
          - otherwise → "needs_review"
        """
        VALID_TYPES = {"correct", "partial", "incorrect"}
        if feedback_type not in VALID_TYPES:
            raise ValueError(f"feedback_type must be one of {VALID_TYPES}, got '{feedback_type}'")

        tmpl = await self.load(template_id)
        if not tmpl:
            return {"error": "template_not_found"}

        # Persist the new feedback record
        fb = TemplateFeedback(
            template_id=template_id,
            user_id=user_id,
            feedback_type=feedback_type,
            element=element,
            correction_json=correction_json,
            notes=notes,
        )
        self.session.add(fb)
        await self.session.flush()  # write fb so it's included in the count below

        # Fetch ALL feedback for this template (including the one just flushed)
        result = await self.session.execute(
            select(TemplateFeedback).where(TemplateFeedback.template_id == template_id)
        )
        all_feedback = list(result.scalars().all())

        score_map = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
        feedback_scores = [score_map[f.feedback_type] for f in all_feedback]
        feedback_avg = sum(feedback_scores) / len(feedback_scores)

        current_confidence = tmpl.confidence_score or 0.0
        n = len(all_feedback)
        if n < 3:
            new_confidence = 0.70 * current_confidence + 0.30 * feedback_avg
        else:
            new_confidence = 0.40 * current_confidence + 0.60 * feedback_avg

        new_confidence = max(0.0, min(1.0, new_confidence))
        if new_confidence >= 0.85:
            new_status = "verified"
        elif tmpl.is_global or tmpl.status == "ready":
            new_status = "verified"  # don't demote published templates
        else:
            new_status = "needs_review"

        await self.session.execute(
            update(Template)
            .where(Template.id == template_id)
            .values(
                confidence_score=new_confidence,
                status=new_status,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

        return {
            "feedback_id": fb.id,
            "template_id": template_id,
            "feedback_count": n,
            "feedback_avg": feedback_avg,
            "current_confidence": current_confidence,
            "new_confidence": new_confidence,
            "new_status": new_status,
        }
