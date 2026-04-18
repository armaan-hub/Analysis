"""
Template CRUD operations using async SQLAlchemy.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Template


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
    ) -> Template:
        """Create or replace a template."""
        config_json = json.dumps(config)
        now = datetime.now(timezone.utc)

        if template_id:
            # Update existing
            await self.session.execute(
                update(Template)
                .where(Template.id == template_id)
                .values(
                    name=name,
                    config_json=config_json,
                    status=status,
                    confidence_score=confidence_score,
                    verification_report=verification_report,
                    page_count=page_count,
                    source_pdf_name=source_pdf_name,
                    updated_at=now,
                )
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
        self, user_id: str, status: Optional[str] = None
    ) -> List[Template]:
        """List all templates for a user, optionally filtered by status."""
        q = select(Template).where(Template.user_id == user_id)
        if status:
            q = q.where(Template.status == status)
        q = q.order_by(Template.updated_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_global_templates(self) -> List[Template]:
        """List globally shared templates."""
        result = await self.session.execute(
            select(Template)
            .where(Template.is_global == True)
            .order_by(Template.updated_at.desc())
        )
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
    ) -> None:
        """Update config, name, status, and confidence of an existing template."""
        stmt = (
            update(Template)
            .where(Template.id == template_id)
            .values(
                config_json=json.dumps(config),
                name=name,
                status=status,
                confidence_score=confidence_score,
                verification_report=verification_report,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    def get_config(self, template: Template) -> dict:
        """Deserialize template config_json to dict."""
        return json.loads(template.config_json)
