"""
Analysis Mode API — Multi-stage document analysis pipeline.
"""
import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import settings, compute_llm_params
from core.document_processor import DocumentProcessor
from core.llm_manager import get_llm_provider
from core.rag_engine import rag_engine, _normalize_chunk

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

document_processor = DocumentProcessor()
_analysis_files: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    file_ids: list[str]
    query: str
    provider: Optional[str] = None


_ANALYSIS_SYSTEM = (
    "You are a UAE-certified chartered accountant and legal compliance expert. "
    "Analyze the provided financial documents and legal references. "
    "Structure your response as:\n"
    "# Financial/Legal Analysis Report\n"
    "## Document(s) Analyzed\n"
    "## Key Findings\n"
    "## Compliance Check (table format: Check | Result | Details)\n"
    "## Detailed Breakdown\n"
    "## Sources\n"
    "## Recommendations\n\n"
    "Cite all sources: 📄 [filename] (row N–M) for spreadsheets, 📄 [filename] (page N) for PDFs."
)


@router.post("/upload")
async def upload_analysis_document(file: UploadFile = File(...)):
    """Upload a financial/legal document for analysis. Returns a file_id."""
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "document").suffix or ".pdf"
    upload_path = Path(settings.upload_dir) / f"analysis_{file_id}{suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with upload_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _analysis_files[file_id] = {
        "file_id": file_id,
        "filename": file.filename,
        "path": str(upload_path),
        "suffix": suffix,
    }
    return {"file_id": file_id, "filename": file.filename}


@router.post("/analyze")
async def analyze_documents(req: AnalyzeRequest):
    """Run multi-stage analysis on uploaded documents + RAG context."""
    if not req.file_ids:
        raise HTTPException(status_code=422, detail="At least one file_id required")

    model_name = settings.nvidia_model
    llm_params = compute_llm_params(model_name=model_name, mode="analyst")
    llm = get_llm_provider(req.provider, mode="analyst")

    doc_sections: list[str] = []
    analyzed_files: list[str] = []

    for file_id in req.file_ids:
        if file_id not in _analysis_files:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        finfo = _analysis_files[file_id]
        path = finfo["path"]
        fname = finfo["filename"] or path
        suffix = finfo["suffix"].lower()

        if suffix == ".csv":
            content = document_processor.batch_extract_csv(path)
        elif suffix in (".xlsx", ".xls"):
            content = document_processor.batch_extract_excel(path)
        else:
            chunks = await document_processor.process(path, doc_id=file_id)
            content = "\n".join(c.text for c in chunks[:8])

        doc_sections.append(f"### {fname}\n{content[:8000]}")
        analyzed_files.append(fname)

    rag_raw = await rag_engine.search(
        req.query,
        top_k=llm_params["top_k"],
        filter={"category": {"$in": ["law", "finance"]}},
        min_score=settings.rag_min_score,
    )
    rag_chunks = [_normalize_chunk(r) for r in rag_raw]
    rag_context = "\n\n".join(
        f"📄 {c['source_file']} (page {c['page']})\n{c.get('text', '')[:400]}"
        for c in rag_chunks
    )

    doc_context = "\n\n".join(doc_sections)
    prompt = (
        f"## Documents Provided\n{doc_context}\n\n"
        f"## Relevant Law & Regulations\n{rag_context}\n\n"
        f"## Analysis Request\n{req.query}"
    )
    messages = [
        {"role": "system", "content": _ANALYSIS_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    response = await llm.chat(messages, temperature=llm_params["temperature"], max_tokens=llm_params["max_tokens"])

    return {
        "report": response.text,
        "files_analyzed": analyzed_files,
        "rag_sources": [
            {"source_file": c["source_file"], "page": c["page"], "score": c.get("score")}
            for c in rag_chunks
        ],
    }
