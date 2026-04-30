"""
APScheduler configuration for regulatory monitoring jobs.
Fetches UAE regulatory sources, compares SHA-256 hashes, and creates Alerts on change.
"""

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from config import settings
from db.database import async_session
from db.models import MonitoredSource, Alert

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# ── Default UAE regulatory sources ───────────────────────────────────────────
DEFAULT_SOURCES = [
    {
        "name": "FTA – News & Updates",
        "url": "https://tax.gov.ae/en/news.aspx",
        "category": "tax",
    },
    {
        "name": "FTA – VAT Legislation",
        "url": "https://tax.gov.ae/en/legislation/vat.legislation.aspx",
        "category": "tax",
    },
    {
        "name": "FTA – Corporate Tax Legislation",
        "url": "https://tax.gov.ae/en/legislation/corporate.tax.legislation.aspx",
        "category": "tax",
    },
    {
        "name": "UAE MoF – Legislation",
        "url": "https://www.mof.gov.ae/en/resourcesAndBudget/Pages/legislation.aspx",
        "category": "finance",
    },
    {
        "name": "UAE MoJ – Legislation Portal",
        "url": "https://uaelegislation.gov.ae/en",
        "category": "law",
    },
    {
        "name": "CBUAE – Circulars",
        "url": "https://www.centralbank.ae/en/index.php/regulations/circulars",
        "category": "finance",
    },
]


_scheduler_running = False


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _log_task_exception(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            f"Background monitoring task failed: {task.exception()}",
            exc_info=task.exception(),
        )


async def seed_default_sources() -> int:
    """Insert DEFAULT_SOURCES if they don't already exist. Returns count added."""
    added = 0
    async with async_session() as db:
        for s in DEFAULT_SOURCES:
            existing = await db.execute(
                select(MonitoredSource).where(MonitoredSource.url == s["url"])
            )
            if existing.scalar_one_or_none() is None:
                db.add(MonitoredSource(
                    id=str(uuid.uuid4()),
                    name=s["name"],
                    url=s["url"],
                    category=s["category"],
                    check_interval_hours=6,
                    is_active=True,
                ))
                added += 1
        await db.commit()
    return added


async def fetch_and_check_updates():
    """Background task: fetch each active source, diff hash, create Alert on change."""
    logger.info("Running scheduled regulatory monitoring checks...")

    async with async_session() as db:
        result = await db.execute(
            select(MonitoredSource).where(MonitoredSource.is_active.is_(True))
        )
        sources = result.scalars().all()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for source in sources:
                try:
                    resp = await client.get(source.url, headers={"User-Agent": "LegalAcctAI-Monitor/1.0"})
                    resp.raise_for_status()
                    content_hash = _sha256(resp.text)

                    changed = (
                        source.last_hash is not None
                        and source.last_hash != content_hash
                    )

                    if changed:
                        logger.info(f"Change detected: {source.name}")
                        alert_id = str(uuid.uuid4())
                        alert = Alert(
                            id=alert_id,
                            source_id=source.id,
                            title=f"Update detected: {source.name}",
                            summary=(
                                f"The page at {source.url} has changed since last check "
                                f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})."
                            ),
                            severity="warning",
                            is_read=False,
                        )
                        db.add(alert)
                        # Push to WebSocket clients immediately
                        try:
                            from api.monitoring import broadcast_alert
                            _task = asyncio.create_task(broadcast_alert({
                                "id": alert_id,
                                "title": alert.title,
                                "source_name": source.name,
                                "summary": alert.summary,
                                "severity": alert.severity,
                                "is_read": False,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            }))
                            _task.add_done_callback(_log_task_exception)
                        except Exception as ws_exc:
                            logger.debug(f"WS broadcast skipped: {ws_exc}")

                    # Update hash and last_checked timestamp
                    source.last_hash = content_hash
                    source.last_checked = datetime.now(timezone.utc)
                    await db.flush()

                except httpx.HTTPStatusError as e:
                    logger.warning(f"HTTP {e.response.status_code} fetching {source.url} — skipping")
                except httpx.RequestError as e:
                    logger.warning(f"Request failed for {source.url}: {e} — skipping")
                except Exception as exc:
                    logger.warning(f"Failed to check {source.name}: {exc}")

        await db.commit()

    logger.info("Completed monitoring check.")


def start_scheduler():
    """Start the APScheduler for periodic checks."""
    global _scheduler_running
    if _scheduler_running:
        logger.warning("Scheduler already running — ignoring duplicate start()")
        return
    _scheduler_running = True
    interval = settings.monitor_interval_hours
    scheduler.add_job(
        fetch_and_check_updates,
        trigger=IntervalTrigger(hours=interval),
        id="monitoring_job",
        replace_existing=True,
    )

    # FTA scraper: auto-download new UAE law PDFs at midnight daily
    from core.pipeline.fta_scraper import scrape_and_ingest
    scheduler.add_job(
        scrape_and_ingest,
        trigger=CronTrigger(hour=0, minute=0),
        id="fta_scraper",
        name="FTA PDF Scraper",
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,    # prevent overlapping runs
    )
    logger.info("Scheduled FTA scraper: daily at midnight")

    scheduler.start()
    logger.info(f"Monitoring scheduler started (interval: {interval} hours)")
