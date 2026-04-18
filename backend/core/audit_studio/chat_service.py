"""Chat service for audit studio. Wraps existing LLM + profile context."""
import json
from db.database import AsyncSessionLocal
from db.models import ProfileVersion, AuditChatMessage
from sqlalchemy import select


async def _current_profile_json(profile_id: str) -> str:
    async with AsyncSessionLocal() as s:
        v = (await s.execute(
            select(ProfileVersion).where(
                ProfileVersion.profile_id == profile_id,
                ProfileVersion.is_current == True,  # noqa: E712
            )
        )).scalar_one_or_none()
    return v.profile_json if v else "{}"


async def run_chat(profile_id: str, user_message: str) -> dict:
    """Return {'content': str, 'citations': list}. Mocked in tests."""
    ctx = await _current_profile_json(profile_id)
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
    prompt = [{"role": "user", "content": (
        "You are an AI audit assistant. Use the following profile JSON as context "
        "and answer the question with citations where possible.\n\n"
        f"PROFILE:\n{ctx}\n\nUSER: {user_message}"
    )}]
    resp = await llm.chat(prompt)
    return {"content": resp.content, "citations": []}


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
