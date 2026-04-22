"""
Chat API – Handles conversations, messages, and RAG-augmented responses.
"""

import asyncio
import io
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, AsyncSessionLocal
from db.models import Conversation, Message, Document
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine
from core.prompt_router import get_system_prompt, route_prompt, DOMAIN_PROMPTS, FORMATTING_REMINDER
from core.chat.domain_classifier import classify_domain, DomainLabel, ClassifierResult
from config import settings
from core.web_search import search_web, build_web_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Type aliases
ConversationMode = Literal["fast", "deep_research", "analyst"]

_RESEARCH_KEYWORDS = {
    "research", "deep analysis", "deep dive", "analyze", "analyse",
    "investigate", "comprehensive", "detailed report", "full breakdown",
    "explain in detail", "in-depth", "in depth", "thorough", "complete guide",
    "everything about", "all about",
}


def _is_research_query(message: str) -> bool:
    """Return True if the message contains research-mode trigger keywords."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _RESEARCH_KEYWORDS)


QUERY_VARIATION_PROMPT = (
    "Generate 2 alternative phrasings for this search query. "
    "Return ONLY a JSON array of strings, no explanation.\n"
    "Query: {query}"
)


async def _get_query_variations(query: str, provider: str | None = None) -> list[str]:
    """Return [original, variation1, variation2]. Falls back to [original] on any error."""
    try:
        llm = get_llm_provider(provider)
        resp = await llm.chat(
            messages=[{"role": "user", "content": QUERY_VARIATION_PROMPT.format(query=query)}],
            max_tokens=150,
            temperature=0.3,
        )
        match = re.search(r'\[.*?\]', resp.content, re.DOTALL)
        if not match:
            return [query]
        variations: list[str] = json.loads(match.group())
        return [query] + [v for v in variations if isinstance(v, str)][:2]
    except Exception:
        return [query]



def _build_sliding_context(
    messages: list,  # list of ChatMessage objects or dicts
    max_messages: int = 20,
    max_tokens_estimate: int = 12000,
) -> list:
    """Build a sliding window of conversation context.

    Takes the most recent `max_messages` messages and trims from the oldest
    if the estimated token count exceeds `max_tokens_estimate`.
    Each ~4 chars ≈ 1 token.
    """
    recent = messages[-max_messages:] if len(messages) > max_messages else list(messages)

    # Estimate tokens and trim from oldest if over budget
    while len(recent) > 2:  # keep at least the last 2 messages
        total_chars = sum(len(getattr(m, 'content', '') or getattr(m, 'message', '') or str(m)) for m in recent)
        estimated_tokens = total_chars // 4
        if estimated_tokens <= max_tokens_estimate:
            break
        recent.pop(0)  # drop oldest message

    return recent


async def extract_and_save_memory(
    conversation_id: str,
    messages: list[dict],
) -> None:
    """Extract memorable facts from a conversation and store in UserMemory."""
    if len(messages) < 4:
        return

    try:
        from db.models import UserMemory

        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:400]}"
            for m in messages[-20:]
        )

        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract factual details from this conversation worth remembering for future sessions. "
                        "Return ONLY a JSON array. Each item: {\"key\": \"string\", \"value\": \"string\", \"confidence\": 0.0-1.0}. "
                        "Keys to extract (only if explicitly stated): company_name, industry, vat_trn, trn_number, "
                        "preferred_language, detail_level, company_location, business_type. "
                        "Do NOT invent. Max 8 items. Return [] if nothing clear is stated."
                    ),
                },
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return
        facts = json.loads(match.group(0))

        async with AsyncSessionLocal() as db:
            for fact in facts:
                key = fact.get("key", "").strip()
                value = fact.get("value", "").strip()
                confidence = float(fact.get("confidence", 1.0))
                if not key or not value or confidence < 0.5:
                    continue

                existing = await db.execute(
                    select(UserMemory).where(
                        UserMemory.user_id == "default",
                        UserMemory.key == key,
                    )
                )
                existing_row = existing.scalar_one_or_none()
                if existing_row:
                    existing_row.value = value
                    existing_row.confidence = confidence
                    existing_row.source_conversation_id = conversation_id
                else:
                    db.add(UserMemory(
                        user_id="default",
                        key=key,
                        value=value,
                        confidence=confidence,
                        source_conversation_id=conversation_id,
                    ))

            await db.commit()
        logger.info(f"Saved {len(facts)} memory facts from conversation {conversation_id}")

    except Exception as exc:
        logger.warning(f"Memory extraction failed (non-fatal): {exc}")


# ── Request / Response Schemas────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming chat message."""
    message: str
    conversation_id: Optional[str] = None
    use_rag: bool = True  # Whether to search documents for context
    provider: Optional[str] = None  # Override provider for this request
    stream: bool = False
    domain: Optional[str] = None  # legacy — used as domain_override if set
    mode: Literal["fast", "deep_research", "analyst"] = "fast"
    domain_override: Optional[str] = None  # DomainLabel value e.g. "vat", "corporate_tax"
    selected_doc_ids: Optional[list[str]] = None  # Restrict RAG/hybrid search to these docs

class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    source_count: int = 0
    domain: Optional[str] = None
    mode: ConversationMode = "fast"

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[list] = None
    created_at: str
    tokens_used: int = 0

class ChatResponse(BaseModel):
    message: MessageResponse
    conversation_id: str
    provider: str
    model: str

class ExportRequest(BaseModel):
    message_id: str
    format: str  # "word" | "pdf" | "excel"


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ConversationOut(BaseModel):
    id: str
    title: str
    mode: ConversationMode
    created_at: str


class ConversationPatch(BaseModel):
    mode: Optional[ConversationMode] = None
    title: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/send", response_model=ChatResponse)
async def send_message(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Send a message and get an AI response."""
    start_time = time.time()

    # Get or create conversation
    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == req.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
            llm_provider=req.provider or settings.llm_provider,
            llm_model=settings.active_model,
            mode=req.mode,
        )
        db.add(conversation)
        await db.flush()

        # Background: extract memory from previous conversation if idle 30+ min
        prev_conv_result = await db.execute(
            select(Conversation)
            .where(Conversation.id != conversation.id)
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        prev_conv = prev_conv_result.scalar_one_or_none()
        if prev_conv:
            now_naive = datetime.utcnow()
            updated_naive = prev_conv.updated_at.replace(tzinfo=None) if prev_conv.updated_at.tzinfo else prev_conv.updated_at
            idle_minutes = (now_naive - updated_naive).total_seconds() / 60
            if idle_minutes >= 30:
                prev_msgs_result = await db.execute(
                    select(Message)
                    .where(
                        Message.conversation_id == prev_conv.id,
                        Message.role.in_(["user", "assistant"]),
                    )
                    .order_by(Message.created_at)
                )
                prev_msgs = [
                    {"role": m.role, "content": m.content}
                    for m in prev_msgs_result.scalars().all()
                ]
                async def _run_memory_extraction():
                    try:
                        await asyncio.wait_for(
                            extract_and_save_memory(prev_conv.id, prev_msgs),
                            timeout=60.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Memory extraction timed out for conversation {prev_conv.id}")
                asyncio.create_task(_run_memory_extraction())

    # Load cross-session memory
    from db.models import UserMemory
    memory_result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == "default")
        .order_by(desc(UserMemory.updated_at))
        .limit(10)
    )
    memory_rows = memory_result.scalars().all()
    memory_block = ""
    if memory_rows:
        memory_lines = [f"- {m.key}: {m.value}" for m in memory_rows]
        memory_block = "\n[Memory from prior sessions]\n" + "\n".join(memory_lines) + "\n"

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    await db.flush()

    # Get conversation history — sliding window of last 20 messages with token budgeting.
    # Fetch most-recent 21 (desc) then reverse to get chronological order.
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(21)  # 21 = 20 prior + 1 just-added user message
    )
    history = list(reversed(history_result.scalars().all()))

    # Build messages list
    messages = []
    sources = []
    search_results = []

    # Domain classification — use override if provided, else run LLM classifier
    effective_override = req.domain_override or req.domain  # backward compat
    if effective_override:
        try:
            classifier_result = ClassifierResult(
                domain=DomainLabel(effective_override),
                confidence=1.0,
                alternatives=[],
            )
        except ValueError:
            # Legacy domain value not in DomainLabel — fall back to LLM classifier
            classifier_result = await classify_domain(req.message)
    else:
        classifier_result = await classify_domain(req.message)

    # Persist domain to conversation on first message
    if not conversation.domain:
        conversation.domain = classifier_result.domain.value

    if req.mode == "analyst":
        system_prompt = DOMAIN_PROMPTS.get("analyst", DOMAIN_PROMPTS["general"]) + memory_block
    else:
        system_prompt = route_prompt(classifier_result.domain) + memory_block

    # If RAG is enabled, search for relevant context
    if req.use_rag:
        # Document-scoped search takes highest priority (user explicitly selected docs)
        rag_filter = None
        if req.selected_doc_ids:
            rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
        elif req.mode != "analyst":
            # Domain-aware RAG: filter by category when domain is finance or law.
            # Analyst mode intentionally skips category filtering to search all documents.
            if req.domain in ("finance",):
                rag_filter = {"category": "finance"}
            elif req.domain in ("law", "audit"):
                rag_filter = {"category": "law"}

        try:
            if req.mode == "fast":
                query_variations = await _get_query_variations(req.message, getattr(req, 'provider', None))
                all_results = await asyncio.gather(
                    *[
                        rag_engine.search(q, top_k=settings.top_k_results, filter=rag_filter)
                        for q in query_variations
                    ],
                    return_exceptions=True,
                )
                seen: set[tuple] = set()
                merged: list = []
                for batch in all_results:
                    if isinstance(batch, Exception):
                        continue
                    for r in batch:
                        key = (r["metadata"].get("doc_id", ""), r["metadata"].get("page", 0))
                        if key not in seen:
                            seen.add(key)
                            merged.append(r)
                search_results = sorted(merged, key=lambda x: x.get("score", 0), reverse=True)[:15]
                # Fall back to unfiltered if domain filter yields nothing
                if rag_filter and not search_results:
                    fallback = await asyncio.gather(
                        *[rag_engine.search(q, top_k=settings.top_k_results) for q in query_variations],
                        return_exceptions=True,
                    )
                    seen2: set[tuple] = set()
                    merged2: list = []
                    for batch in fallback:
                        if isinstance(batch, Exception):
                            continue
                        for r in batch:
                            key = (r["metadata"].get("doc_id", ""), r["metadata"].get("page", 0))
                            if key not in seen2:
                                seen2.add(key)
                                merged2.append(r)
                    search_results = sorted(merged2, key=lambda x: x.get("score", 0), reverse=True)[:15]
            else:
                search_results = await rag_engine.search(
                    req.message, top_k=settings.top_k_results, filter=rag_filter
                )
                # If strict domain filter yields no matches, fall back to unfiltered
                # retrieval so chat still uses available indexed context.
                if rag_filter and not search_results:
                    search_results = await rag_engine.search(
                        req.message, top_k=settings.top_k_results
                    )
        except Exception as rag_exc:
            logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
            search_results = []


        if search_results:
            augmented = rag_engine.build_augmented_prompt(
                req.message, search_results, system_prompt=system_prompt
            )
            messages.append(augmented[0])  # system message with context
            sources = [
                {
                    "source": r.get("source") or r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown"),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                }
                for r in search_results
            ]
        else:
            messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({"role": "system", "content": system_prompt})

    # Inject structured text from small xlsx/csv documents
    try:
        if search_results:
            doc_sources = {r["metadata"].get("source", "") for r in search_results if r.get("metadata")}
            if doc_sources:
                st_result = await db.execute(
                    select(Document).where(Document.filename.in_(doc_sources))
                )
                for d in st_result.scalars().all():
                    meta = d.metadata_json if isinstance(d.metadata_json, dict) else {}
                    st = meta.get("structured_text")
                    if st:
                        messages[0]["content"] += (
                            f"\n\n[Full structured data from {d.original_name}]\n{st}"
                        )
    except Exception as e:
        logger.warning(f"Structured text enrichment failed: {e}")

    # Add conversation history (skip the last user message since we add it separately)
    # Apply sliding window with token budgeting to the history
    trimmed_history = _build_sliding_context(history[:-1])
    for msg in trimmed_history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message (with formatting reminder for fast mode)
    if req.mode == "fast":
        messages.append({"role": "system", "content": FORMATTING_REMINDER})
    messages.append({"role": "user", "content": req.message})

    # Call LLM
    try:
        llm = get_llm_provider(req.provider)

        if req.stream:
            # For streaming, return SSE response
            async def generate():
                nonlocal sources  # allow modification inside nested function

                # First event: metadata
                meta: dict = {
                    "type": "meta",
                    "conversation_id": conversation.id,
                    "detected_domain": classifier_result.domain.value,
                    "classifier": classifier_result.model_dump(),
                    "mode": req.mode,
                }
                yield f"data: {json.dumps(meta)}\n\n"

                # If RAG returned nothing, try web search
                if not search_results:
                    is_research = _is_research_query(req.message)
                    if is_research:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'researching', 'message': 'Deep research in progress…'})}\n\n"
                        from core.web_search import deep_search
                        web_results = await deep_search(req.message, max_queries=6)
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web'})}\n\n"
                        web_results = await search_web(req.message, max_results=5)
                    if web_results:
                        web_context = build_web_context(web_results)
                        if is_research:
                            web_instruction = (
                                "IMPORTANT: You have comprehensive research results from multiple sources below. "
                                "Synthesize ALL sources into a well-structured response. "
                                "Use numbered sections with bold headings. "
                                "Cite sources as [Source Name] inline where relevant. "
                                "Be thorough — the user asked for deep research.\n\n"
                                + web_context
                            )
                        else:
                            web_instruction = (
                                "IMPORTANT: Answer ONLY using the web search results provided below. "
                                "Do not add information from your training data. "
                                "Cite the source URLs inline. Take your time and be accurate.\n\n"
                                + web_context
                            )
                        # Replace the system message with web-augmented version
                        messages[0] = {"role": "system", "content": system_prompt + "\n\n" + web_instruction}
                        # Build sources list from web results
                        sources = [
                            {
                                "source": r.get("href", ""),
                                "page": "web",
                                "score": 1.0,
                                "excerpt": r.get("body", "")[:200],
                                "is_web": True,
                            }
                            for r in web_results
                        ]
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'web_search_failed'})}\n\n"

                full_response = ""
                try:
                    async for chunk in llm.chat_stream(
                        messages,
                        temperature=settings.temperature,
                        max_tokens=settings.max_tokens,
                    ):
                        full_response += chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                except Exception as stream_exc:
                    err = repr(stream_exc) if str(stream_exc) == '' else f"{type(stream_exc).__name__}: {stream_exc}"
                    logger.error(f"LLM streaming error: {err}")
                    yield f"data: {json.dumps({'type': 'error', 'message': err})}\n\n"
                    return

                if sources:
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

                # TODO: auto-ingest web results when ingest_text method is available

                # Save assistant message after streaming completes
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                    sources=sources if sources else None,
                )
                db.add(assistant_msg)
                await db.commit()
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
            )

        # Non-streaming response
        response = await llm.chat(
            messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except Exception as e:
        import httpx as _httpx
        elapsed = round(time.time() - start_time, 1)
        err_msg = repr(e) if str(e) == '' else f"{type(e).__name__}: {e}"
        exc_lower = str(e).lower() + type(e).__name__.lower()

        # Check HTTP status code first (avoids false matches on URL strings)
        http_status = getattr(getattr(e, "response", None), "status_code", None)
        if http_status in (401, 403):
            error_code = "AUTH"
        elif http_status == 429:
            error_code = "RATE_LIMIT"
        elif isinstance(e, (_httpx.TimeoutException,)) or "timeout" in exc_lower:
            error_code = "TIMEOUT"
        elif isinstance(e, (_httpx.ConnectError,)) or "connect" in exc_lower or "network" in exc_lower:
            error_code = "NETWORK"
        else:
            error_code = "PROVIDER_ERROR"

        logger.error(f"LLM [{error_code}] {elapsed}s — {err_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"[{error_code}] {err_msg} (elapsed: {elapsed}s, provider: {req.provider or settings.llm_provider})",
        )

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response.content,
        sources=sources if sources else None,
        tokens_used=response.tokens_used,
    )
    db.add(assistant_msg)
    await db.flush()
    await db.commit()

    return ChatResponse(
        message=MessageResponse(
            id=assistant_msg.id,
            role="assistant",
            content=response.content,
            sources=sources if sources else None,
            created_at=str(assistant_msg.created_at),
            tokens_used=response.tokens_used,
        ),
        conversation_id=conversation.id,
        provider=response.provider,
        model=response.model,
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all conversations, newest first."""
    result = await db.execute(
        select(Conversation)
        .order_by(desc(Conversation.updated_at))
        .offset(offset)
        .limit(limit)
    )
    conversations = result.scalars().all()

    response = []
    for conv in conversations:
        # Count messages efficiently
        msg_count_result = await db.execute(
            select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
        )
        msg_count = msg_count_result.scalar_one()

        # Count checked sources
        source_count = 0
        if conv.checked_source_ids:
            source_count = len(conv.checked_source_ids) if isinstance(conv.checked_source_ids, list) else len(json.loads(conv.checked_source_ids or "[]"))

        response.append(ConversationResponse(
            id=conv.id,
            title=conv.title,
            created_at=str(conv.created_at),
            updated_at=str(conv.updated_at),
            message_count=msg_count,
            source_count=source_count,
            domain=conv.domain,
            mode=conv.mode,
        ))

    return response


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationCreate, db: AsyncSession = Depends(get_db)):
    """Create a new conversation."""
    conv = Conversation(title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        mode=conv.mode,
        created_at=str(conv.created_at)
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single conversation."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        mode=conv.mode,
        created_at=str(conv.created_at)
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: str,
    patch: ConversationPatch,
    db: AsyncSession = Depends(get_db)
):
    """Update a conversation (mode, title, etc.)."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if patch.mode is not None:
        conv.mode = patch.mode
    if patch.title is not None:
        conv.title = patch.title
    await db.commit()
    await db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        mode=conv.mode,
        created_at=str(conv.created_at)
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a conversation."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            sources=msg.sources,
            created_at=str(msg.created_at),
            tokens_used=msg.tokens_used,
        )
        for msg in messages
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.commit()
    return {"status": "deleted", "conversation_id": conversation_id}


@router.post("/export")
async def export_message(req: ExportRequest, db: AsyncSession = Depends(get_db)):
    """Export a chat message as Word, PDF, or Excel file."""
    from core.export_converter import to_word, to_pdf, to_excel
    from fastapi.responses import Response

    # Fetch the message
    result = await db.execute(
        select(Message).where(Message.id == req.message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    content = message.content or ""

    if req.format == "word":
        file_bytes = to_word(content)
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=response.docx"},
        )
    elif req.format == "pdf":
        file_bytes = to_pdf(content)
        return Response(
            content=file_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=response.pdf"},
        )
    elif req.format == "excel":
        file_bytes = to_excel(content)
        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="No tables found in this message. Excel export requires a table.",
            )
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=response.xlsx"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")


# ── Deep Research Export ──────────────────────────────────────────

class DeepResearchExportRequest(BaseModel):
    content: str
    sources: list[dict] = Field(default_factory=list)
    format: Literal["pdf", "docx", "xlsx"]
    query: str


@router.post("/export-deep-research")
async def export_deep_research(req: DeepResearchExportRequest):
    """Export deep-research results as a branded PDF, DOCX, or XLSX file."""
    from core.deep_research_export import to_branded_pdf, to_branded_docx, to_branded_xlsx

    if req.format == "pdf":
        file_bytes = to_branded_pdf(req.content, req.sources, req.query)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=deep_research_report.pdf"},
        )
    elif req.format == "docx":
        file_bytes = to_branded_docx(req.content, req.sources, req.query)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=deep_research_report.docx"},
        )
    elif req.format == "xlsx":
        file_bytes = to_branded_xlsx(req.content, req.sources, req.query)
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=deep_research_report.xlsx"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")


# ── Deep Research Endpoint ────────────────────────────────────────────────────

class DeepResearchRequest(BaseModel):
    conversation_id: Optional[str] = None
    query: str
    selected_doc_ids: Optional[list[str]] = None


@router.post("/deep-research")
async def deep_research_stream(req: DeepResearchRequest):
    """Dedicated deep-research SSE endpoint: RAG + web synthesis with progress steps."""
    from core.rag_engine import rag_engine
    from core.web_search import deep_search

    async def generate():
        try:
            # Step 1: Search indexed documents
            doc_sources: list[dict] = []
            if req.selected_doc_ids:
                yield f"data: {json.dumps({'type': 'step', 'text': f'Searching {len(req.selected_doc_ids)} selected document(s)…'})}\n\n"
                doc_filter = {"doc_id": {"$in": req.selected_doc_ids}}
                raw = await rag_engine.search(req.query, top_k=10, filter=doc_filter)
            else:
                yield f"data: {json.dumps({'type': 'step', 'text': 'Searching all indexed documents…'})}\n\n"
                raw = await rag_engine.search(req.query, top_k=10)

            rag_context_parts: list[str] = []
            for r in raw:
                meta = r.get("metadata") or {}
                fname = meta.get("original_name") or meta.get("source") or "document"
                page = meta.get("page_number") or meta.get("page") or 1
                snippet = r.get("text", "")[:600]
                rag_context_parts.append(f"[{fname}, p.{page}]\n{snippet}")
                doc_sources.append({"filename": fname, "page": page})

            # Step 2: Web research
            yield f"data: {json.dumps({'type': 'step', 'text': 'Running deep web research…'})}\n\n"
            web_results = await deep_search(req.query, max_queries=5)
            web_sources: list[dict] = []
            web_context_parts: list[str] = []
            for w in web_results or []:
                url = w.get("href") or w.get("url", "")
                title = w.get("title", url)
                body = w.get("body", "")[:500]
                web_sources.append({"title": title, "url": url})
                web_context_parts.append(f"[{title}]({url})\n{body}")

            # Step 3: Synthesize
            yield f"data: {json.dumps({'type': 'step', 'text': 'Synthesising answer…'})}\n\n"
            llm = get_llm_provider()
            system = (
                "You are a thorough research analyst. Synthesise the provided document excerpts and "
                "web search results into a comprehensive, well-structured answer. Use Markdown with "
                "## headings and bullet points. Cite sources inline as (Source Name) or [Source URL]."
            )
            context_block = ""
            if rag_context_parts:
                context_block += "## Document Context\n" + "\n\n".join(rag_context_parts) + "\n\n"
            if web_context_parts:
                context_block += "## Web Research\n" + "\n\n".join(web_context_parts) + "\n\n"

            messages_for_llm = [
                {"role": "system", "content": system},
                {"role": "user", "content": context_block + f"## Question\n{req.query}"},
            ]
            answer_parts: list[str] = []
            async for chunk in llm.chat_stream(messages_for_llm, temperature=0.3, max_tokens=2000):
                answer_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            full_answer = "".join(answer_parts)
            yield f"data: {json.dumps({'type': 'answer', 'content': full_answer, 'sources': doc_sources, 'web_sources': web_sources})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Deep research error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
