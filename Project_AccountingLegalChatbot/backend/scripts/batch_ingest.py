"""
Standalone async batch ingest script.

Processes ALL documents in source_law_dir and source_finance_dir through the
existing ingest pipeline, embedding them into ChromaDB + SQLite.

Usage (from project root):
    python3 backend/scripts/batch_ingest.py
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is on sys.path when run from project root
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import settings  # noqa: E402
from db.database import AsyncSessionLocal  # noqa: E402
from db.models import Document  # noqa: E402

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx"}
LOG_PATH = Path(__file__).parent / "ingest_log.json"


def collect_source_files() -> list[tuple[Path, str]]:
    """Return all supported files from law and finance source dirs.

    Each entry is (file_path, source_dir_label) where source_dir_label is
    "law" or "finance".
    """
    results: list[tuple[Path, str]] = []
    for label, dir_str in (("law", settings.source_law_dir), ("finance", settings.source_finance_dir)):
        directory = Path(dir_str)
        if not directory.exists():
            print(f"[WARN] Source directory does not exist: {directory}")
            continue
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                results.append((file_path, label))
    return results


def compute_sha256(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


async def is_already_indexed(file_path: Path, db) -> bool:
    """Return True if a Document with matching content_hash and indexed_at exists."""
    from sqlalchemy import select

    content_hash = compute_sha256(file_path)
    result = await db.execute(
        select(Document).where(
            Document.content_hash == content_hash,
            Document.indexed_at.is_not(None),
        )
    )
    return result.scalar_one_or_none() is not None


def save_progress_log(
    total: int,
    processed: int,
    skipped: int,
    errors: int,
    error_details: list[dict],
) -> None:
    """Write a JSON progress log to scripts/ingest_log.json."""
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details,
    }
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))


async def _probe_model(base_url: str, api_key: str, model: str, timeout: float = 8.0) -> bool:
    """Return True if model responds with HTTP < 400 within timeout seconds."""
    import httpx
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=6.0, read=timeout, write=6.0, pool=5.0)
        ) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            )
            return resp.status_code < 400
    except Exception:
        return False


async def _patch_fast_llm_for_batch() -> None:
    """Probe NVIDIA LLM endpoints and patch extract_metadata + entity-graph to use
    the first working provider.  Priority: main → devstral → mistral-small-fallback → skip-LLM.

    This ensures batch ingest never hangs waiting on a degraded/unresponsive model.
    """
    from core import llm_manager as _lm_mod
    from core.llm_manager import NvidiaProvider
    from config import settings

    mgr = _lm_mod.llm_manager
    base_url = mgr._provider.base_url
    main_key = mgr._provider.api_key
    main_model = mgr._provider.model

    # Fast-model credentials from settings (separate key if configured)
    fast_model = getattr(settings, "nvidia_fast_model", "") or ""
    fast_key = getattr(settings, "nvidia_fast_api_key", "") or main_key
    fallback_model = getattr(settings, "nvidia_fast_fallback_model", "") or ""

    print("[INFO] Probing NVIDIA LLM models for batch ingest...")

    # 1. Try main model
    if await _probe_model(base_url, main_key, main_model, timeout=8.0):
        print(f"[INFO] Main model ({main_model}) is responsive — no patch needed.")
        return

    print(f"[WARN] Main model ({main_model}) unresponsive.")

    # Find the first working fast/fallback provider
    working_provider = None
    for model_name, api_key in [
        (fast_model, fast_key),
        (fallback_model, fast_key),
        (fallback_model, main_key),
    ]:
        if not model_name or model_name == main_model:
            continue
        if await _probe_model(base_url, api_key, model_name, timeout=8.0):
            print(f"[INFO] Using fallback model: {model_name}")
            working_provider = NvidiaProvider(
                api_key=api_key, model=model_name, base_url=base_url, thinking_enabled=False
            )
            break
        else:
            print(f"[WARN] Fallback model {model_name} also unavailable.")

    if working_provider is None:
        print("[WARN] No LLM available — metadata extraction will return empty results; embedding will proceed.")

    # Patch LLMManager.extract_metadata to use working_provider (or return empty if None)
    _META_SYSTEM = (
        "You are a UAE legal research assistant. Analyze this document and extract metadata. "
        "Return ONLY valid JSON with these fields: "
        "domain (one of: tenancy|vat|corporate_tax|aml|competition|banking_compliance|labour|"
        "antidumping|trademark|copyright|consumer_protection|companies|general|other), "
        "jurisdiction (uae_federal|dubai|cabinet|ministerial|local), "
        "law_number (official law/decree number or empty string), "
        "subjects (array of 3-8 specific legal topics), "
        "effective_date (ISO date or null), "
        "summary (1-2 sentence plain-English summary)."
    )

    _wp = working_provider  # capture for closure

    async def _patched_extract_metadata(self, filename, text, source_dir):
        import json as _json
        from core.llm_manager import MetadataResult
        if _wp is None:
            return MetadataResult()
        try:
            response = await asyncio.wait_for(
                _wp.chat(
                    [{"role": "system", "content": _META_SYSTEM},
                     {"role": "user", "content": f"Filename: {filename}\nSource: {source_dir}\n\n{text[:2000]}"}],
                    temperature=0.1, max_tokens=512,
                ),
                timeout=20.0,
            )
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = _json.loads(raw)
            return MetadataResult(
                domain=data.get("domain", "general") or "general",
                jurisdiction=data.get("jurisdiction", "") or "",
                law_number=data.get("law_number", "") or "",
                subjects=data.get("subjects", []) or [],
                effective_date=data.get("effective_date") or None,
                summary=data.get("summary", "") or "",
            )
        except Exception:
            return MetadataResult()

    _lm_mod.LLMManager.extract_metadata = _patched_extract_metadata

    # Set fast provider for entity-graph extraction in document_processor.py
    _lm_mod._BATCH_FAST_PROVIDER = working_provider  # None means entity graph will be skipped


async def run_batch_ingest() -> None:
    import logging as _logging
    _logging.basicConfig(
        level=_logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )

    from core.document_processor import DocumentProcessor

    await _patch_fast_llm_for_batch()
    document_processor = DocumentProcessor()

    files = collect_source_files()
    total = len(files)

    processed = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    print(f"Found {total} source files. Starting ingest...\n", flush=True)

    for idx, (file_path, source_dir) in enumerate(files, start=1):
        label = f"[{idx}/{total}]"
        filename = file_path.name

        async with AsyncSessionLocal() as db:
            try:
                if await is_already_indexed(file_path, db):
                    print(f"[SKIP] {filename}", flush=True)
                    skipped += 1
                    continue

                print(f"{label} Processing: {filename} ...", flush=True)
                await asyncio.wait_for(
                    document_processor.ingest_source_file(str(file_path), source_dir, db),
                    timeout=300.0,  # 5-minute hard cap per file (prevents hangs on degraded APIs)
                )
                print(f"[OK] {filename}", flush=True)
                processed += 1

            except BaseException as exc:
                err_msg = f"{type(exc).__name__}: {exc}"
                print(f"[ERROR] {filename}: {err_msg}", flush=True)
                import traceback as _tb
                _tb.print_exc()
                sys.stdout.flush()
                error_details.append({"file": str(file_path), "error": err_msg})
                errors += 1
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise  # propagate fatal signals

        # Rate-limit to avoid overwhelming the NVIDIA API
        await asyncio.sleep(0.5)

    save_progress_log(total, processed, skipped, errors, error_details)

    print("\n=== Ingest Complete ===", flush=True)
    print(f"Total files found:     {total}", flush=True)
    print(f"Already indexed:       {skipped}", flush=True)
    print(f"Successfully ingested: {processed}", flush=True)
    print(f"Errors:                {errors}", flush=True)
    print("Log saved to: scripts/ingest_log.json", flush=True)


if __name__ == "__main__":
    import signal as _signal
    # Ignore SIGHUP — prevents terminal disconnect from killing a long-running batch job
    try:
        _signal.signal(_signal.SIGHUP, _signal.SIG_IGN)
    except (AttributeError, OSError):
        pass  # SIGHUP not available on all platforms

    try:
        asyncio.run(run_batch_ingest())
    except BaseException as exc:
        import traceback as _tb
        print(f"\n[FATAL] Uncaught {type(exc).__name__}: {exc}", flush=True)
        _tb.print_exc()
        sys.exit(1)
