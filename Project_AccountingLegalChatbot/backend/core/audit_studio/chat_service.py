"""Chat service for audit studio. Wraps existing LLM + profile context."""
import json
import logging
from db.database import AsyncSessionLocal
from db.models import ProfileVersion, AuditChatMessage
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def _current_profile_json(profile_id: str) -> str:
    async with AsyncSessionLocal() as s:
        v = (await s.execute(
            select(ProfileVersion).where(
                ProfileVersion.profile_id == profile_id,
                ProfileVersion.is_current.is_(True),
            )
        )).scalar_one_or_none()
    return v.profile_json if v else "{}"


async def _load_history(profile_id: str) -> list[dict]:
    """Return last 10 messages for this profile as [{role, content}]."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(AuditChatMessage)
            .where(AuditChatMessage.profile_id == profile_id)
            .order_by(AuditChatMessage.created_at.desc())
            .limit(10)
        )).scalars().all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


async def run_chat(profile_id: str, user_message: str, source_ids: list[str] | None = None) -> dict:
    """Return {'content': str, 'citations': list}. Mocked in tests."""
    ctx = await _current_profile_json(profile_id)
    history = await _load_history(profile_id)

    # RAG retrieval with graceful fallback
    from core.rag_engine import rag_engine
    rag_results = []
    try:
        rag_filter = {"doc_id": {"$in": source_ids}} if source_ids else None
        rag_results = await rag_engine.search(user_message, top_k=5, filter=rag_filter)
    except Exception:
        logger.warning("RAG search failed; continuing without retrieved context.", exc_info=True)

    # Build system message using the structured audit domain prompt
    from core.prompt_router import get_system_prompt
    rag_context = "\n\n".join(
        f"Source: {r['source']}, Page: {r.get('page', 1)}\n\nExcerpt: {r['excerpt']}"
        for r in rag_results
    )
    audit_base = get_system_prompt("audit", user_message)
    system_content = (
        f"{audit_base}\n\n"
        "Use the profile JSON and any retrieved document excerpts below as context, "
        "and answer with citations where possible.\n\n"
        f"PROFILE:\n{ctx}"
    )
    if rag_context:
        system_content += f"\n\nRELEVANT DOCUMENTS:\n{rag_context}"

    from config import settings
    from core.llm_manager import NvidiaProvider, OpenAIProvider, ClaudeProvider
    provider = settings.llm_provider.lower()
    if provider == "openai":
        llm = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    elif provider in ("anthropic", "claude"):
        llm = ClaudeProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    else:
        llm = NvidiaProvider(
            api_key=settings.nvidia_api_key,
            model=settings.nvidia_model,
            base_url=settings.nvidia_base_url,
        )

    prompt = (
        [{"role": "system", "content": system_content}]
        + history
        + [{"role": "user", "content": user_message}]
    )
    resp = await llm.chat(prompt)

    citations = [
        {
            "doc_id": r["metadata"].get("doc_id", r["source"]),
            "source": r["source"],
            "page": r.get("page", 1),
        }
        for r in rag_results
        if r.get("score", 1.0) >= 0.6
    ]
    return {"content": resp.content, "citations": citations}


async def persist_exchange(profile_id: str, user_msg: str, assistant_reply: dict) -> None:
    async with AsyncSessionLocal() as s:
        s.add(AuditChatMessage(profile_id=profile_id, role="user", content=user_msg))
        s.add(AuditChatMessage(
            profile_id=profile_id,
            role="assistant",
            content=assistant_reply["content"],
            citations=json.dumps(assistant_reply.get("citations", [])),
        ))
        await s.commit()
