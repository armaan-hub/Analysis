"""Simple async event bus for research job progress."""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global dict: job_id → asyncio.Queue of events.
# WARNING: This is an in-process registry. It only works correctly with a
# single uvicorn worker. In multi-worker deployments the POST that creates
# the channel may land on a different worker than the SSE GET, causing 404s.
# For horizontal scaling, replace this with Redis Pub/Sub or a similar
# cross-process message broker.
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
