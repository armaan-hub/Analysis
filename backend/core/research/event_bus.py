"""Simple async event bus for research job progress."""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global dict: job_id → asyncio.Queue of events
_queues: dict[str, asyncio.Queue] = {}


def create_channel(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues[job_id] = q
    return q


def get_channel(job_id: str) -> asyncio.Queue | None:
    return _queues.get(job_id)


async def emit(job_id: str, event: dict[str, Any]) -> None:
    q = _queues.get(job_id)
    if q:
        await q.put(event)


def remove_channel(job_id: str) -> None:
    _queues.pop(job_id, None)
