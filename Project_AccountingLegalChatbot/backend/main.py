
"""
Accounting & Legal AI Chatbot – FastAPI Application Entry Point.

Run with: uvicorn main:app --host 0.0.0.0 --port 8080 --reload
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("chatbot")

# ── App Lifecycle ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("=" * 60)
    logger.info("  Accounting & Legal AI Chatbot – Starting...")
    logger.info("=" * 60)

    # Initialize database tables
    from db.database import init_db
    await init_db()
    logger.info("[OK] Database initialized")

    # Seed account-mapping cache from bundled CSV (INSERT OR IGNORE — safe to re-run)
    from pathlib import Path
    from core.agents.account_cache import seed_from_csv, cache_size
    _csv = Path("data/account_grouping_labels.csv")
    if _csv.exists():
        _seeded = await seed_from_csv(_csv)
        logger.info(f"[OK] Account mapping cache: {_seeded} CSV rows processed, {await cache_size()} total entries")

    # Log config
    from config import settings
    logger.info(f"[OK] LLM Provider: {settings.llm_provider} ({settings.active_model})")
    logger.info(f"[OK] RAG Vector Store: {settings.vector_store_dir}")
    logger.info(f"[OK] Upload Directory: {settings.upload_dir}")
    logger.info(f"[OK] Server: http://{settings.host}:{settings.port}")
    
    # Start APScheduler
    from monitoring.scheduler import start_scheduler, scheduler
    start_scheduler()
    
    logger.info("=" * 60)

    yield

    logger.info("Chatbot server shutting down...")
    scheduler.shutdown()


# ── FastAPI App ───────────────────────────────────────────────────

app = FastAPI(
    title="Accounting & Legal AI Chatbot",
    description=(
        "Multi-platform AI chatbot for accounting and legal professionals. "
        "Features RAG-powered document analysis, financial report generation, "
        "and regulatory monitoring."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API Routers ─────────────────────────────────────────
from api.chat import router as chat_router
from api.documents import router as documents_router
from api.reports import router as reports_router
from api.monitoring import router as monitoring_router
from api.settings import router as settings_router
from api.audit_profiles import router as audit_profiles_router
from api.templates import router as templates_router

app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(reports_router)
app.include_router(monitoring_router)
app.include_router(settings_router)
app.include_router(audit_profiles_router)
app.include_router(templates_router)


# ── Root Endpoint ─────────────────────────────────────────────────

@app.get("/")
async def root():
    """Health check / welcome endpoint."""
    from config import settings
    from core.rag_engine import rag_engine

    return {
        "app": "Accounting & Legal AI Chatbot",
        "version": "1.0.0",
        "status": "running",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.active_model,
        "documents_indexed": rag_engine.get_stats()["total_chunks"],
        "endpoints": {
            "chat": "/api/chat/send",
            "documents": "/api/documents/",
            "reports_ifrs": "/api/reports/generate/ifrs",
            "reports_vat": "/api/reports/generate/vat",
            "reports_corptax": "/api/reports/generate/corptax",
            "monitoring_alerts": "/api/monitoring/alerts",
            "monitoring_trigger": "/api/monitoring/trigger",
            "settings": "/api/settings/current",
            "settings_switch_provider": "/api/settings/providers/switch",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


# ── Run directly ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
