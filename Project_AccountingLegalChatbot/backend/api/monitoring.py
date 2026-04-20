"""
Monitoring API – Manages regulatory sources and alerts.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import logging
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import MonitoredSource, Alert

logger = logging.getLogger(__name__)

# ── WebSocket connection registry ─────────────────────────────────────────────
_connected_clients: list[WebSocket] = []

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])

# ── Schemas ───────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name: str
    url: str
    category: str = "general"
    check_interval_hours: int = 6

class SourceResponse(BaseModel):
    id: str
    name: str
    url: str
    category: str
    is_active: bool
    check_interval_hours: int
    last_checked: Optional[str] = None
    created_at: str

class AlertResponse(BaseModel):
    id: str
    source_name: str
    title: str
    summary: Optional[str]
    diff_content: Optional[str]
    severity: str
    is_read: bool
    created_at: str

# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/sources", response_model=SourceResponse)
async def add_source(req: SourceCreate, db: AsyncSession = Depends(get_db)):
    """Add a new website/url to monitor."""
    new_source = MonitoredSource(
        name=req.name,
        url=req.url,
        category=req.category,
        check_interval_hours=req.check_interval_hours
    )
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    
    return SourceResponse(
        id=new_source.id,
        name=new_source.name,
        url=new_source.url,
        category=new_source.category,
        is_active=new_source.is_active,
        check_interval_hours=new_source.check_interval_hours,
        created_at=str(new_source.created_at)
    )

@router.get("/sources", response_model=List[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all monitored sources."""
    result = await db.execute(select(MonitoredSource))
    sources = result.scalars().all()
    
    return [
        SourceResponse(
            id=s.id,
            name=s.name,
            url=s.url,
            category=s.category,
            is_active=s.is_active,
            check_interval_hours=s.check_interval_hours,
            last_checked=str(s.last_checked) if s.last_checked else None,
            created_at=str(s.created_at)
        ) for s in sources
    ]

@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(unread_only: bool = False, db: AsyncSession = Depends(get_db)):
    """List regulatory change alerts."""
    stmt = select(Alert, MonitoredSource).join(MonitoredSource).order_by(desc(Alert.created_at))
    if unread_only:
        stmt = stmt.where(Alert.is_read.is_(False))
        
    result = await db.execute(stmt)
    records = result.all()
    
    return [
        AlertResponse(
            id=alert.id,
            source_name=source.name,
            title=alert.title,
            summary=alert.summary,
            diff_content=alert.diff_content,
            severity=alert.severity,
            is_read=alert.is_read,
            created_at=str(alert.created_at)
        ) for alert, source in records
    ]

@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, db: AsyncSession = Depends(get_db)):
    """Mark an alert as read."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert.is_read = True
    await db.commit()
    return {"status": "success"}

@router.post("/seed-sources")
async def seed_default_sources():
    """Seed the default UAE regulatory sources (FTA, MoF, MoJ, CBUAE)."""
    from monitoring.scheduler import seed_default_sources as _seed
    added = await _seed()
    return {"status": "ok", "sources_added": added}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a monitored source."""
    result = await db.execute(select(MonitoredSource).where(MonitoredSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted"}


@router.post("/trigger")
async def trigger_monitoring():
    """Manually trigger the monitoring job."""
    from monitoring.scheduler import fetch_and_check_updates
    asyncio.create_task(fetch_and_check_updates())
    return {"status": "triggered", "message": "Monitoring checks started in the background."}


# ── WebSocket: real-time alert push ──────────────────────────────────────────

@router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket):
    """
    Persistent WebSocket connection.
    The server pushes {"type": "alert", "data": {...}} when a new regulatory
    change is detected by the scheduler.
    """
    await websocket.accept()
    _connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_connected_clients)}")
    try:
        while True:
            # Keep-alive ping every 30 s; also allows disconnect detection
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in _connected_clients:
            _connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(_connected_clients)}")


async def broadcast_alert(alert_data: dict) -> None:
    """
    Push a new regulatory alert to all connected WebSocket clients.
    Called by the scheduler when a new alert is written to the DB.
    Dead connections are removed silently.
    """
    dead: list[WebSocket] = []
    for ws in list(_connected_clients):
        try:
            await ws.send_json({"type": "alert", "data": alert_data})
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _connected_clients:
            _connected_clients.remove(ws)
