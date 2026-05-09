"""Internal-only LLM helper endpoints (not in public Swagger)."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/llm", tags=["llm-internal"])


class TranslateRequest(BaseModel):
    text: str
    source_language: str = "ar"
    target_language: str = "en"


class TranslateResponse(BaseModel):
    translated_text: str
    detected_language: str


class MetadataRequest(BaseModel):
    filename: str
    text: str
    source_dir: str


class MetadataResponse(BaseModel):
    domain: str
    jurisdiction: str
    law_number: str
    subjects: list[str]
    effective_date: Optional[str]
    summary: str


@router.post("/translate", response_model=TranslateResponse, include_in_schema=False)
async def translate_text(req: TranslateRequest) -> TranslateResponse:
    from core.llm_manager import llm_manager
    try:
        translated = await llm_manager.translate(req.text, src=req.source_language, tgt=req.target_language)
        return TranslateResponse(translated_text=translated, detected_language=req.source_language)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/extract-metadata", response_model=MetadataResponse, include_in_schema=False)
async def extract_metadata(req: MetadataRequest) -> MetadataResponse:
    from core.llm_manager import llm_manager
    try:
        result = await llm_manager.extract_metadata(filename=req.filename, text=req.text, source_dir=req.source_dir)
        return MetadataResponse(
            domain=result.domain, jurisdiction=result.jurisdiction,
            law_number=result.law_number, subjects=result.subjects,
            effective_date=result.effective_date, summary=result.summary,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
