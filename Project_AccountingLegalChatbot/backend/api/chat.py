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
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, AsyncSessionLocal
from db.models import Conversation, Message, Document
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine, _infer_domain_from_name
from core.prompt_router import get_system_prompt, route_prompt, DOMAIN_PROMPTS, FORMATTING_REMINDER
from core.chat.domain_classifier import classify_domain, DomainLabel, ClassifierResult
from core.chat.intent_classifier import classify_intent
from pathlib import Path as _Path
from core.rag.hybrid_retriever import HybridRetriever
from core.rag.graph_rag import GraphRAG
from config import settings
from core.web_search import search_web, build_web_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _build_hybrid_retriever() -> HybridRetriever:
    return HybridRetriever(
        rag_engine=rag_engine,
        graph_rag=GraphRAG(str(_Path(settings.graph_store_dir) / "graph.db")),
    )


_hybrid_retriever = _build_hybrid_retriever()

# Type aliases
ConversationMode = Literal["fast", "deep_research", "analyst"]

_RESEARCH_KEYWORDS = {
    "research", "deep analysis", "deep dive", "analyze", "analyse",
    "investigate", "comprehensive", "detailed report", "full breakdown",
    "explain in detail", "in-depth", "in depth", "thorough", "complete guide",
    "everything about", "all about",
}

_TITLE_GENERATION_DELAY_S: float = 0.1  # allow send_message's DB commit to propagate

# Minimum classifier confidence to apply domain filtering to RAG search.
# Below this threshold we fall back to category-only search (search all domains).
_DOMAIN_FILTER_MIN_CONFIDENCE: float = 0.60

# Retry threshold: if best domain-filtered score is below this, retry without domain filter.
# Intentionally above _DOMAIN_FILTER_MIN_CONFIDENCE (0.60) — if classifier confidence
# was low enough to skip domain filtering, we won't reach here anyway.
_BROAD_FALLBACK_THRESHOLD: float = 0.39  # 0.6 × 0.65 — calibrated for combined_score scale

# Minimum relevance score for general_law/general queries (no domain filter applied).
# Below this, finance-corpus results are likely false positives — e.g., VAT real-estate
# docs scoring ~0.69 on "draft wills for estate" because "estate/properties" match.
# Suppressing them lets the LLM answer from general legal knowledge instead.
_GENERAL_LAW_MIN_RELEVANCE_SCORE: float = 0.35  # law docs score 0.40-0.57 combined; 0.35 allows genuine results through while blocking truly irrelevant results

# Maps classified domain label → document domain values to include in RAG filter.
# "general" / "general_law" are intentionally absent — they mean "search all domains".
_DOMAIN_TO_DOC_DOMAINS: dict[str, list[str]] = {
    "e_invoicing": ["e_invoicing", "peppol"],
    "peppol": ["peppol", "e_invoicing"],
    "vat": ["vat"],
    "corporate_tax": ["corporate_tax"],
    "labour": ["labour"],
    "commercial": ["commercial"],
    "ifrs": ["ifrs", "general"],
}


def _build_rag_domain_filter(cls_result: ClassifierResult, base_filter: dict) -> dict:
    """Merge a domain filter into the base category filter if confidence is high enough.

    Returns the original base_filter unchanged when:
    - Confidence is below threshold
    - Domain maps to "search all" (general / general_law)
    - Domain would produce an identical filter to base_filter
    """
    doc_domains = _DOMAIN_TO_DOC_DOMAINS.get(cls_result.domain.value)
    if not doc_domains or cls_result.confidence < _DOMAIN_FILTER_MIN_CONFIDENCE:
        return base_filter

    domain_clause = {"domain": {"$in": doc_domains}}

    # If base_filter already has an $and list, append to it
    if "$and" in base_filter:
        return {"$and": base_filter["$and"] + [domain_clause]}

    # Wrap base_filter + domain_clause together
    return {"$and": [base_filter, domain_clause]}


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
    """Return [original, variation1, variation2]. Falls back to [original] on any error.

    Uses fast model — query variation is a simple paraphrasing task.
    """
    words = query.split()
    # Skip variations for very short queries (too little context) 
    # or very long queries (already specific enough, variations add noise).
    if len(words) <= 3 or len(words) > 15:
        return [query]
    try:
        llm = get_llm_provider(provider, mode="fast")
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


def _dedup_merge(batches: list, top_k: int) -> list:
    """Deduplicate and merge RAG result batches, returning top-k by score."""
    seen: set[tuple] = set()
    merged: list = []
    for batch in batches:
        if isinstance(batch, Exception):
            continue
        for r in batch:
            key = (
                r["metadata"].get("doc_id") or r.get("text", "")[:80],
                r["metadata"].get("page", 0)
            )
            if key not in seen:
                seen.add(key)
                merged.append(r)
    return sorted(merged, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

async def _get_or_refresh_summary(conversation_id: str, history_count: int, provider: str | None = None) -> None:
    """Summarise oldest messages when conversation grows beyond 20 turns. Non-fatal."""
    if history_count <= 20:
        return
    try:
        async with AsyncSessionLocal() as db:
            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            if conv is None:
                return
            if history_count <= (conv.summary_msg_count or 0) + 10:
                return  # Not enough new messages to re-summarise
            old_count = history_count - 20
            old_messages = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
                .limit(old_count)
            )).scalars().all()
            if not old_messages:
                return
            context = "\n".join(
                f"{m.role.upper()}: {m.content[:400]}" for m in old_messages
            )
            llm = get_llm_provider(provider, mode="fast")  # summary is a routine text task
            resp = await llm.chat(
                messages=[{
                    "role": "user",
                    "content": (
                        "Summarise the following conversation excerpt in 3-5 sentences, "
                        "capturing the main topics and conclusions:\n\n" + context
                    ),
                }],
                max_tokens=600,
                temperature=0.1,
            )
            conv.summary = resp.content
            conv.summary_msg_count = history_count
            await db.commit()
    except Exception as exc:
        logger.warning(f"Session summary failed for {conversation_id}: {exc}")



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

        llm = get_llm_provider(mode="fast")  # memory extraction is a lightweight structured task
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


_TITLE_PROMPT = (
    "Summarise the following user query as a short notebook title "
    "(maximum 8 words, Title Case). "
    "Return ONLY the title — no punctuation at the end, no quotation marks.\n"
    "Query: {message}"
)


async def _generate_title(conversation_id: str, message: str, provider: str | None = None) -> None:
    """Generate a short AI title for a new conversation and persist it. Non-fatal."""
    await asyncio.sleep(_TITLE_GENERATION_DELAY_S)  # defensive: let send_message's DB commit propagate
    try:
        llm = get_llm_provider(provider, mode="fast")  # title generation is lightweight
        resp = await llm.chat(
            messages=[{"role": "user", "content": _TITLE_PROMPT.format(message=message[:400])}],
            max_tokens=30,
            temperature=0.2,
        )
        title = re.sub(r'^[`*_"\'\s]+|[`*_"\'\s.]+$', '', resp.content.strip())
        if not title:
            return
        title = title[:100]
        async with AsyncSessionLocal() as db:
            conv = (await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )).scalar_one_or_none()
            if conv:
                conv.title = title
                await db.commit()
    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)


# ── Request / Response Schemas────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming chat message."""
    message: str = Field(..., min_length=1, description="The user's chat message (must not be empty)")
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
async def send_message(req: ChatRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Send a message and get an AI response."""
    start_time = time.time()

    # Get or create conversation
    _title_args: tuple[str, str, str | None] | None = None  # set when new conversation created
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
        # Store args; task is scheduled AFTER db.commit() so the row is visible to _generate_title
        _title_args = (conversation.id, req.message, req.provider)

        # Background: extract memory from previous conversation if idle 30+ min
        prev_conv_result = await db.execute(
            select(Conversation)
            .where(Conversation.id != conversation.id)
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        prev_conv = prev_conv_result.scalar_one_or_none()
        if prev_conv:
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
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

    if req.stream:
        async def generate():  # noqa: C901
            # ── 1. Domain classification ──────────────────────────────────────
            _eff = req.domain_override or req.domain
            if _eff:
                try:
                    _cls = ClassifierResult(
                        domain=DomainLabel(_eff), confidence=1.0, alternatives=[]
                    )
                except ValueError:
                    _cls = await classify_domain(req.message)
            else:
                _cls = await classify_domain(req.message)

            if not conversation.domain:
                conversation.domain = _cls.domain.value

            # ── 2. Yield meta (client gets first byte here, ~1-2 s) ───────────
            _meta_payload = json.dumps({
                "type": "meta",
                "conversation_id": conversation.id,
                "detected_domain": _cls.domain.value,
                "classifier": _cls.model_dump(),
                "mode": req.mode,
            })
            yield f"data: {_meta_payload}\n\n"

            # ── 3. System prompt ───────────────────────────────────────────────
            if req.mode == "analyst":
                _sys = DOMAIN_PROMPTS.get("analyst", DOMAIN_PROMPTS["general"]) + memory_block
            else:
                _sys = route_prompt(_cls.domain) + memory_block
            if req.mode == "fast" and getattr(conversation, "summary", None):
                _sys += f"\n\nCONTEXT SUMMARY OF EARLIER CONVERSATION:\n{conversation.summary}"

            # ── 4. Intent + query variations in parallel ──────────────────────
            _llm = get_llm_provider(req.provider, mode=req.mode)
            _reasoning_effort = (
                settings.nvidia_fast_reasoning_effort if req.mode == "fast" else None
            )
            _intent_task = asyncio.create_task(classify_intent(req.message, _llm))
            if req.mode == "fast":
                _vars_task = asyncio.create_task(
                    _get_query_variations(req.message, req.provider)
                )
                _intent_res, _query_vars = await asyncio.gather(
                    _intent_task, _vars_task, return_exceptions=True
                )
            else:
                _intent_res = await _intent_task
                _query_vars = [req.message]

            if not isinstance(_intent_res, Exception):
                _sys += (
                    f"\n\nUSER INTENT: The user wants a `{_intent_res.output_type}` "
                    f"about `{_intent_res.topic}`. "
                    "Respond ONLY in that form. Do not produce a different output type. "
                    "Stay strictly on topic; do not drift to related but unasked subjects."
                )
            else:
                logger.warning("Intent classification failed (non-fatal): %s", _intent_res)

            if isinstance(_query_vars, Exception):
                _query_vars = [req.message]

            # ── 5. RAG search ─────────────────────────────────────────────────
            _rag_filter: dict | None = None
            _base_filter: dict = {"category": {"$in": ["law", "finance"]}}
            _doc_scoped = False
            _search_results: list = []
            _sources: list = []

            if req.use_rag:
                if req.selected_doc_ids:
                    if req.mode == "analyst":
                        # Analyst mode: search within selected docs only (client workbooks are valid here)
                        _rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
                        _doc_scoped = True
                    else:
                        # Fast/Deep: scope to selected docs but only professional knowledge base
                        _base_filter: dict = {
                            "$and": [
                                {"doc_id": {"$in": req.selected_doc_ids}},
                                {"category": {"$in": ["law", "finance"]}},
                            ]
                        }
                        _rag_filter = _build_rag_domain_filter(_cls, _base_filter)
                else:
                    _base_filter = {"category": {"$in": ["law", "finance"]}}
                    _rag_filter = _build_rag_domain_filter(_cls, _base_filter)

                try:
                    _search_results = await _hybrid_retriever.retrieve(
                        query=req.message,
                        top_k=settings.fast_top_k if req.mode == "fast" else settings.top_k_results,
                        rag_filter=_rag_filter,
                    )
                except Exception as _rag_exc:
                    logger.warning("RAG search failed, falling back to no-context mode: %s", _rag_exc)
                    _search_results = []

                # ------ broad-search fallback ------
                # Check if a domain filter WAS applied and results are weak
                _broad_fallback_used = False
                _domain_filter_applied = (
                    _rag_filter is not None
                    and (
                        ("domain" in _rag_filter)
                        or ("$and" in _rag_filter and any("domain" in c for c in _rag_filter["$and"]))
                    )
                )
                if _domain_filter_applied and not _doc_scoped:
                    _top_score = max((r.get("combined_score", r.get("score", 0)) for r in _search_results), default=0.0) if _search_results else 0.0
                    _top_score_raw = max((r.get("score", 0) for r in _search_results), default=0.0) if _search_results else 0.0
                    if not _search_results or _top_score < _BROAD_FALLBACK_THRESHOLD:
                        try:
                            # Retry with base filter only (no domain filter)
                            if req.mode == "fast":
                                _broad_all = await asyncio.gather(
                                    *[rag_engine.search(
                                        q,
                                        top_k=settings.fast_top_k,
                                        filter=_base_filter,
                                        min_score=settings.rag_min_score,
                                    ) for q in _query_vars],
                                    return_exceptions=True,
                                )
                                _broad_results = _dedup_merge(_broad_all, settings.fast_top_k)
                            else:
                                _broad_results = await rag_engine.search(
                                    req.message,
                                    top_k=settings.top_k_results,
                                    filter=_base_filter,
                                    min_score=settings.rag_min_score,
                                )
                            # Use broad results if they score better
                            if _broad_results:
                                _broad_top = max((r.get("score", 0) for r in _broad_results), default=0.0)
                                if _broad_top > _top_score_raw:
                                    _search_results = _broad_results
                                    _broad_fallback_used = True
                                    logger.info(
                                        f"Broad fallback: domain-filtered top score {_top_score:.2f} < {_BROAD_FALLBACK_THRESHOLD}, "
                                        f"broad top score {_broad_top:.2f} used instead"
                                    )
                                else:
                                    logger.debug(
                                        f"Broad fallback available (top={_broad_top:.3f}) but discarded "
                                        f"— current results stronger (raw={_top_score_raw:.3f})"
                                    )
                        except Exception as _fallback_exc:
                            logger.warning(f"Broad fallback search failed (non-fatal): {_fallback_exc}")
                # ------ end fallback ------

                # ------ cross-domain contamination guard ------
                # After broad fallback, if returned results belong to a different
                # domain than the one queried (e.g., VAT docs for corporate_tax),
                # suppress them. Applies to every domain in _DOMAIN_TO_DOC_DOMAINS.
                # general_law/general are intentionally absent from that map and are
                # handled by _GENERAL_LAW_MIN_RELEVANCE_SCORE below.
                _queried_doc_domains = set(_DOMAIN_TO_DOC_DOMAINS.get(_cls.domain.value, []))
                _GENERAL_DOMAINS = {"general", "general_law", ""}
                if _domain_filter_applied and _broad_fallback_used and _queried_doc_domains and _search_results:
                    _domain_matching = [
                        r for r in _search_results
                        if r.get("metadata", {}).get("domain") in _queried_doc_domains
                        or r.get("metadata", {}).get("domain", "") in _GENERAL_DOMAINS
                    ]
                    if not _domain_matching:
                        logger.info(
                            "Cross-domain suppression (stream): cleared %d results "
                            "(domains=%s) for %s query — none matched %s",
                            len(_search_results),
                            {r.get("metadata", {}).get("domain") for r in _search_results},
                            _cls.domain.value,
                            _queried_doc_domains,
                        )
                        _search_results = []
                    elif len(_domain_matching) < len(_search_results):
                        logger.info(
                            "Cross-domain partial filter (stream): kept %d/%d results for %s",
                            len(_domain_matching), len(_search_results), _cls.domain.value,
                        )
                        _search_results = _domain_matching
                # ------ end cross-domain guard ------

                # ------ general_law false-positive suppression ------
                # When domain=general_law the filter has no domain clause, so finance-corpus
                # docs (VAT real-estate, etc.) can score ~0.40-0.41 on legal queries simply
                # because of overlapping words like "estate/properties/million".
                # Law docs (post re-ingest) score 0.40-0.57 combined_score and rank #1 above
                # finance false-positives; threshold 0.35 lets genuine law results through
                # while still suppressing truly irrelevant results (score < 0.35).
                # If every result is below _GENERAL_LAW_MIN_RELEVANCE_SCORE we treat them
                # as false positives and clear them so the LLM answers from general knowledge.
                if (
                    not _doc_scoped
                    and not _domain_filter_applied
                    and _cls.domain.value in ("general_law", "general")
                    and _search_results
                ):
                    _gl_top = max((r.get("combined_score", r.get("score", 0)) for r in _search_results), default=0.0)
                    if _gl_top < _GENERAL_LAW_MIN_RELEVANCE_SCORE:
                        logger.info(
                            f"Suppressing {len(_search_results)} low-relevance finance sources "
                            f"for {_cls.domain.value} query (top score {_gl_top:.2f} < "
                            f"{_GENERAL_LAW_MIN_RELEVANCE_SCORE})"
                        )
                        _search_results = []
                # ------ end suppression ------

                logger.info("RAG returned %d results for conversation %s", len(_search_results), conversation.id)

            # No-LLM guard: doc-scoped query with zero chunks → honest refusal
            from core.accuracy.citation_validator import should_skip_llm
            if should_skip_llm(_search_results, _doc_scoped):
                _no_ctx_content = "I don't have this in my documents."
                no_ctx_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=_no_ctx_content,
                    sources=None,
                )
                db.add(no_ctx_msg)
                await db.flush()
                await db.commit()
                yield f"data: {json.dumps({'type': 'chunk', 'content': _no_ctx_content})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': no_ctx_msg.id})}\n\n"
                return

            # ── 6. Build messages list ────────────────────────────────────────
            _msgs: list[dict] = []
            if _search_results:
                _aug = rag_engine.build_augmented_prompt(
                    req.message, _search_results, system_prompt=_sys
                )
                _msgs.append(_aug[0])

                def _sanitize_rag_source(src: str) -> str:
                    """Remove non-URL source strings that look like filenames."""
                    if not src:
                        return "Unknown"
                    # If it looks like a URL (starts with http/s), return as-is
                    if src.startswith(("http://", "https://")):
                        return src
                    # Otherwise return filename/metadata string (not a URL)
                    return src

                _sources = [
                    {
                        "source": _sanitize_rag_source(
                            r.get("source")
                            or r["metadata"].get("original_name")
                            or r["metadata"].get("source", "Unknown")
                        ),
                        "page": r["metadata"].get("page", "?"),
                        "score": round(r.get("combined_score", r.get("score", 0)), 3),
                        "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                        "domain": r["metadata"].get("domain", ""),
                    }
                    for r in _search_results
                ]
            else:
                _msgs.append({"role": "system", "content": _sys})

            # ── 7. Structured text injection ──────────────────────────────────
            try:
                if _search_results:
                    _doc_srcs = {
                        r["metadata"].get("source", "")
                        for r in _search_results
                        if r.get("metadata")
                    }
                    if _doc_srcs:
                        _st_res = await db.execute(
                            select(Document).where(Document.filename.in_(_doc_srcs))
                        )
                        for _d in _st_res.scalars().all():
                            _meta_d = _d.metadata_json if isinstance(_d.metadata_json, dict) else {}
                            _st = _meta_d.get("structured_text")
                            if _st:
                                _msgs[0]["content"] += (
                                    f"\n\n[Full structured data from {_d.original_name}]\n{_st}"
                                )
            except Exception as _e:
                logger.warning("Structured text enrichment failed: %s", _e)

            # Add conversation history
            _th = _build_sliding_context(history[:-1])
            for _m in _th:
                _msgs.append({"role": _m.role, "content": _m.content})
            # Append formatting reminder to the system message (not as a separate mid-conversation system role,
            # which causes HTTP 400 on Mistral/OpenAI-compatible APIs when placed after user/assistant turns)
            if req.mode == "fast":
                _msgs[0]["content"] += f"\n\n{FORMATTING_REMINDER}"
            _msgs.append({"role": "user", "content": req.message})

            # ── 8. Web search fallback (if no RAG results) ───────────────────
            if not _search_results and not _doc_scoped:
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
                    _url_rule = (
                        "CRITICAL URL RULE: Only include hyperlinks for URLs that are EXPLICITLY listed in the "
                        "search results above. NEVER invent, guess, or reconstruct a URL from a company name. "
                        "If a source does not have a URL in the results, mention the company name as plain text only — "
                        "do NOT add a link. Use the exact URL string from the result, do not modify it."
                    )
                    if is_research:
                        web_instruction = (
                            "IMPORTANT: You have comprehensive research results from multiple sources below. "
                            "Synthesize ALL sources into a well-structured response. "
                            "Use numbered sections with bold headings. "
                            "When citing sources, use markdown hyperlinks in the format [Title](url) — copy the exact URL from the source. "
                            f"Be thorough — the user asked for deep research.\n\n{_url_rule}\n\n"
                            + web_context
                        )
                    else:
                        web_instruction = (
                            "IMPORTANT: Answer ONLY using the web search results provided below. "
                            "Do not add information from your training data. "
                            "When citing sources, use markdown hyperlinks in the format [Title](url) — copy the exact URL from each source. "
                            f"Take your time and be accurate.\n\n{_url_rule}\n\n"
                            + web_context
                        )
                    _msgs[0] = {"role": "system", "content": _sys + "\n\n" + web_instruction}
                    _sources = [
                        {
                            "source": r.get("href", ""),
                            "page": "web",
                            "score": 1.0,
                            "excerpt": r.get("body", "")[:200],
                            "is_web": True,
                            "title": r.get("title", ""),
                        }
                        for r in web_results
                    ]
                else:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'web_search_failed'})}\n\n"

            # ── 9. Stream LLM response ────────────────────────────────────────
            full_response = ""
            _requested_max = settings.fast_max_tokens if req.mode == "fast" else settings.max_tokens
            _safe_max = _llm.compute_safe_max_tokens(_msgs, _requested_max)
            try:
                async for chunk in _llm.chat_stream(
                    _msgs,
                    temperature=settings.fast_temperature if req.mode == "fast" else settings.deep_temperature if req.mode in ("analyst", "deep_research") else settings.temperature,
                    max_tokens=_safe_max,
                    reasoning_effort=_reasoning_effort,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as stream_exc:
                raw = str(stream_exc)
                logger.error("LLM streaming error: %s", raw)
                # Translate HTTP errors into user-friendly messages
                import httpx as _httpx
                if isinstance(stream_exc, _httpx.HTTPStatusError):
                    status = stream_exc.response.status_code
                    if status == 400:
                        _err_body = raw.upper()
                        if "DEGRADED" in _err_body:
                            user_msg = "The AI model is temporarily unavailable (service degraded). Please try again in a few minutes."
                        else:
                            user_msg = "The AI could not process this request (request too large or invalid). Please try a shorter message."
                    elif status == 401:
                        user_msg = "AI API authentication failed. Please check your API key in Settings."
                    elif status == 429:
                        user_msg = "AI API rate limit reached. Please wait a moment and try again."
                    elif status >= 500:
                        user_msg = "The AI service is temporarily unavailable. Please try again shortly."
                    else:
                        user_msg = f"AI API error (HTTP {status}). Please try again."
                elif isinstance(stream_exc, (_httpx.TimeoutException, _httpx.ConnectError)):
                    user_msg = "Connection to AI service timed out. Please check your network and try again."
                else:
                    user_msg = "An unexpected error occurred. Please try again."
                yield f"data: {json.dumps({'type': 'error', 'message': user_msg})}\n\n"
                return

            if not full_response:
                logger.warning("LLM returned empty response for conversation %s", conversation.id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'The AI returned an empty response. Please try again.'})}\n\n"
                return

            # Citation validation
            from core.accuracy.citation_validator import validate_citations, strip_hallucinated_urls
            full_response = validate_citations(full_response, _search_results)

            # Strip any markdown hyperlinks whose URL was not in the supplied sources
            _allowed_urls = {s.get("source", "") for s in _sources} | {s.get("href", "") for s in _sources}
            _allowed_urls.discard("")
            full_response = strip_hallucinated_urls(full_response, _allowed_urls)

            # ── 10. Sources + web auto-ingest ─────────────────────────────────
            if _sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': _sources})}\n\n"
                from core.document_processor import ingest_text
                _web_category = "finance" if _cls.domain.value == "finance" else "law"
                for s in _sources:
                    if s.get("is_web") and s.get("source") and s.get("excerpt"):
                        asyncio.create_task(
                            ingest_text(
                                f"{s.get('source')}\n\n{s.get('excerpt')}",
                                source=s.get("source"),
                                source_type="research",
                                category=_web_category,
                            )
                        )

            # ── 11. Save assistant message ────────────────────────────────────
            try:
                _last_tokens = getattr(_llm, "_last_stream_tokens", None)
                _stream_tokens = _last_tokens if isinstance(_last_tokens, int) else 0
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                    sources=_sources if _sources else None,
                    tokens_used=_stream_tokens,
                )
                db.add(assistant_msg)
                await db.flush()
                total_msg_count = await db.scalar(
                    select(func.count()).select_from(Message).where(
                        Message.conversation_id == conversation.id
                    )
                )
                await db.commit()
                if req.mode == "fast":
                    asyncio.create_task(
                        _get_or_refresh_summary(conversation.id, total_msg_count, req.provider)
                    )
                if _title_args:
                    background_tasks.add_task(_generate_title, *_title_args)
                yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id})}\n\n"
            except Exception as _db_exc:
                logger.error("DB save failed after streaming: %s", _db_exc)
                try:
                    await db.rollback()
                except Exception:
                    pass
                yield f"data: {json.dumps({'type': 'error', 'message': 'Response streamed but could not be saved'})}\n\n"
                return

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

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

    if req.mode == "fast" and getattr(conversation, "summary", None):
        system_prompt += f"\n\nCONTEXT SUMMARY OF EARLIER CONVERSATION:\n{conversation.summary}"

    # Two-pass intent classification: inject output-type directive into system prompt
    llm = get_llm_provider(req.provider, mode=req.mode)  # shared by intent classifier and main LLM; mode selects fast vs. main model
    _reasoning_effort = (
        settings.nvidia_fast_reasoning_effort if req.mode == "fast" else None
    )
    try:
        intent = await classify_intent(req.message, llm)
        intent_directive = (
            f"\n\nUSER INTENT: The user wants a `{intent.output_type}` about `{intent.topic}`. "
            f"Respond ONLY in that form. Do not produce a different output type. "
            f"Stay strictly on topic; do not drift to related but unasked subjects."
        )
        system_prompt = system_prompt + intent_directive
    except Exception as exc:
        logger.warning("Intent classification failed (non-fatal): %s", exc)

    # If RAG is enabled, search for relevant context
    if req.use_rag:
        rag_filter = None
        _base_filter: dict = {"category": {"$in": ["law", "finance"]}}
        if req.selected_doc_ids:
            if req.mode == "analyst":
                # Analyst mode: search within selected docs only (client workbooks are valid here)
                rag_filter = {"doc_id": {"$in": req.selected_doc_ids}}
            else:
                # Fast/Deep: scope to selected docs but only professional knowledge base
                _base_filter = {
                    "$and": [
                        {"doc_id": {"$in": req.selected_doc_ids}},
                        {"category": {"$in": ["law", "finance"]}},
                    ]
                }
                rag_filter = _build_rag_domain_filter(classifier_result, _base_filter)
        else:
            # Default: search professional knowledge base, narrowed by detected domain
            _base_filter = {"category": {"$in": ["law", "finance"]}}
            rag_filter = _build_rag_domain_filter(classifier_result, _base_filter)

        try:
            query_variations = (
                await _get_query_variations(req.message, req.provider)
                if req.mode == "fast"
                else [req.message]
            )
            search_results = await _hybrid_retriever.retrieve(
                query=req.message,
                top_k=settings.fast_top_k if req.mode == "fast" else settings.top_k_results,
                rag_filter=rag_filter,
            )
        except Exception as rag_exc:
            logger.warning(f"RAG search failed, falling back to no-context mode: {rag_exc}")
            search_results = []
            query_variations = [req.message]

        # ------ broad-search fallback ------
        # Check if a domain filter WAS applied and results are weak
        _broad_fallback_used_ns = False
        _domain_filter_applied = (
            rag_filter is not None
            and (
                ("domain" in rag_filter)
                or ("$and" in rag_filter and any("domain" in c for c in rag_filter["$and"]))
            )
        )
        _doc_scoped_ns = req.mode == "analyst" and bool(req.selected_doc_ids)
        if _domain_filter_applied and not _doc_scoped_ns:
            _top_score = max((r.get("combined_score", r.get("score", 0)) for r in search_results), default=0.0) if search_results else 0.0
            _top_score_raw = max((r.get("score", 0) for r in search_results), default=0.0) if search_results else 0.0
            if not search_results or _top_score < _BROAD_FALLBACK_THRESHOLD:
                try:
                    # Retry with base filter only (no domain filter)
                    if req.mode == "fast":
                        _broad_all = await asyncio.gather(
                            *[
                                rag_engine.search(
                                    q,
                                    top_k=settings.fast_top_k,
                                    filter=_base_filter,
                                    min_score=settings.rag_min_score,
                                )
                                for q in query_variations
                            ],
                            return_exceptions=True,
                        )
                        _broad_results = _dedup_merge(_broad_all, settings.fast_top_k)
                    else:
                        _broad_results = await rag_engine.search(
                            req.message,
                            top_k=settings.top_k_results,
                            filter=_base_filter,
                            min_score=settings.rag_min_score,
                        )
                    # Use broad results if they score better
                    if _broad_results:
                        _broad_top = max((r.get("score", 0) for r in _broad_results), default=0.0)
                        if _broad_top > _top_score_raw:
                            search_results = _broad_results
                            _broad_fallback_used_ns = True
                            logger.info(
                                f"Broad fallback: domain-filtered top score {_top_score:.2f} < {_BROAD_FALLBACK_THRESHOLD}, "
                                f"broad top score {_broad_top:.2f} used instead"
                            )
                        else:
                            logger.debug(
                                f"Broad fallback available (top={_broad_top:.3f}) but discarded "
                                f"— current results stronger (raw={_top_score_raw:.3f})"
                            )
                except Exception as fallback_exc:
                    logger.warning(f"Broad fallback search failed (non-fatal): {fallback_exc}")
        # ------ end fallback ------

        # ------ cross-domain contamination guard ------
        _queried_doc_domains_ns = set(_DOMAIN_TO_DOC_DOMAINS.get(classifier_result.domain.value, []))
        _GENERAL_DOMAINS_NS = {"general", "general_law", ""}
        if _domain_filter_applied and _broad_fallback_used_ns and _queried_doc_domains_ns and search_results:
            _domain_matching_ns = [
                r for r in search_results
                if r.get("metadata", {}).get("domain") in _queried_doc_domains_ns
                or r.get("metadata", {}).get("domain", "") in _GENERAL_DOMAINS_NS
            ]
            if not _domain_matching_ns:
                logger.info(
                    "Cross-domain suppression (non-stream): cleared %d results "
                    "(domains=%s) for %s query — none matched %s",
                    len(search_results),
                    {r.get("metadata", {}).get("domain") for r in search_results},
                    classifier_result.domain.value,
                    _queried_doc_domains_ns,
                )
                search_results = []
            elif len(_domain_matching_ns) < len(search_results):
                logger.info(
                    "Cross-domain partial filter (non-stream): kept %d/%d results for %s",
                    len(_domain_matching_ns), len(search_results), classifier_result.domain.value,
                )
                search_results = _domain_matching_ns
        # ------ end cross-domain guard ------

        # ------ general_law false-positive suppression ------
        # Same logic as streaming path — see comment there for rationale.
        if (
            not _doc_scoped_ns
            and not _domain_filter_applied
            and classifier_result.domain.value in ("general_law", "general")
            and search_results
        ):
            _gl_top = max((r.get("combined_score", r.get("score", 0)) for r in search_results), default=0.0)
            if _gl_top < _GENERAL_LAW_MIN_RELEVANCE_SCORE:
                logger.info(
                    f"Suppressing {len(search_results)} low-relevance finance sources "
                    f"for {classifier_result.domain.value} query (top score {_gl_top:.2f} < "
                    f"{_GENERAL_LAW_MIN_RELEVANCE_SCORE})"
                )
                search_results = []
        # ------ end suppression ------

        # No-LLM guard: doc-scoped query with zero chunks → honest refusal
        from core.accuracy.citation_validator import should_skip_llm
        if should_skip_llm(search_results, _doc_scoped_ns):
            _no_ctx = "I don't have this in my documents."
            no_ctx_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=_no_ctx,
                sources=None,
            )
            db.add(no_ctx_msg)
            await db.flush()
            await db.commit()
            return ChatResponse(
                message=MessageResponse(
                    id=no_ctx_msg.id,
                    role="assistant",
                    content=_no_ctx,
                    sources=None,
                    created_at=str(no_ctx_msg.created_at),
                    tokens_used=0,
                ),
                conversation_id=conversation.id,
                provider=settings.llm_provider,
                model=settings.active_model,
            )


        if search_results:
            augmented = rag_engine.build_augmented_prompt(
                req.message, search_results, system_prompt=system_prompt
            )
            messages.append(augmented[0])  # system message with context

            def _sanitize_rag_source(src: str) -> str:
                """Remove non-URL source strings that look like filenames."""
                if not src:
                    return "Unknown"
                if src.startswith(("http://", "https://")):
                    return src
                return src

            sources = [
                {
                    "source": _sanitize_rag_source(r.get("source") or r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown")),
                    "page": r["metadata"].get("page", "?"),
                    "score": round(r.get("combined_score", r.get("score", 0)), 3),
                    "excerpt": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                    "domain": r["metadata"].get("domain", ""),
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

    # Add current user message
    # Formatting reminder goes into system message (not as a separate role mid-conversation,
    # which causes HTTP 400 on Mistral/OpenAI-compatible APIs)
    if req.mode == "fast":
        messages[0]["content"] += f"\n\n{FORMATTING_REMINDER}"
    messages.append({"role": "user", "content": req.message})

    # Call LLM
    _requested_max = settings.fast_max_tokens if req.mode == "fast" else settings.max_tokens
    _safe_max = llm.compute_safe_max_tokens(messages, _requested_max)
    try:
        # Non-streaming response
        response = await llm.chat(
            messages,
            temperature=settings.fast_temperature if req.mode == "fast" else settings.deep_temperature if req.mode in ("analyst", "deep_research") else settings.temperature,
            max_tokens=_safe_max,
            reasoning_effort=_reasoning_effort,
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

    # Citation validation: outside LLM try, owns its own failure surface
    from core.accuracy.citation_validator import validate_citations, strip_hallucinated_urls
    answer_content = validate_citations(response.content, search_results)

    # Strip hallucinated hyperlinks not present in known sources
    _allowed_urls = {s.get("source", "") for s in sources} | {s.get("href", "") for s in sources}
    _allowed_urls.discard("")
    answer_content = strip_hallucinated_urls(answer_content, _allowed_urls)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_content,
        sources=sources if sources else None,
        tokens_used=response.tokens_used,
    )
    db.add(assistant_msg)
    await db.flush()
    total_msg_count = await db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    await db.commit()
    if req.mode == "fast":
        background_tasks.add_task(
            _get_or_refresh_summary, conversation.id, total_msg_count, req.provider
        )
    # Schedule via BackgroundTasks so it runs after get_db's session.commit()
    # cleanup, guaranteeing the Conversation row is visible when _generate_title
    # opens its own AsyncSessionLocal session.
    if _title_args:
        background_tasks.add_task(_generate_title, *_title_args)

    return ChatResponse(
        message=MessageResponse(
            id=assistant_msg.id,
            role="assistant",
            content=answer_content,
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
                # Deep research is always professional context — combine with law+finance to prevent contamination
                doc_filter = {
                    "$and": [
                        {"doc_id": {"$in": req.selected_doc_ids}},
                        {"category": {"$in": ["law", "finance"]}},
                    ]
                }
                raw = await rag_engine.search(
                    req.query, top_k=10, filter=doc_filter,
                    min_score=settings.rag_min_score,
                )
            else:
                yield f"data: {json.dumps({'type': 'step', 'text': 'Searching law & finance knowledge base…'})}\n\n"
                raw = await rag_engine.search(
                    req.query,
                    top_k=10,
                    filter={"category": {"$in": ["law", "finance"]}},
                    min_score=settings.rag_min_score,
                )

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
            try:
                web_results = await asyncio.wait_for(deep_search(req.query, max_queries=5), timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning("Deep web search timed out — continuing with RAG results only")
                web_results = []
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
            llm = get_llm_provider(mode="analyst")
            system = (
                "You are a thorough research analyst. Synthesise the provided document excerpts and "
                "web search results into a comprehensive, well-structured answer. Use Markdown with "
                "## headings and bullet points. When citing web sources, use markdown hyperlinks in the "
                "format [Title](url) — copy the exact URL from the source as provided. "
                "CRITICAL URL RULE: Only include hyperlinks for URLs explicitly listed in the web results above. "
                "NEVER invent, guess, or reconstruct a URL from a company name. If no URL was provided for a "
                "company or source, mention it as plain text only — no link. "
                "For document sources, cite as (Document Name, p.N)."
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
            async for chunk in llm.chat_stream(messages_for_llm, temperature=settings.deep_temperature, max_tokens=2000):
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

