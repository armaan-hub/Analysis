"""Auto-sync watchdog: monitors data folders and ingests new PDFs automatically.

Drop a PDF into data_source_law/ or data_source_finance/ and it will be
ingested into the RAG pipeline within ~10 seconds (debounce window).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

_WATCH_DIRS: list[tuple[Path, str]] = [
    (Path(__file__).parent.parent.parent / "data_source_law", "law"),
    (Path(__file__).parent.parent.parent / "data_source_finance", "finance"),
]

_DEBOUNCE_SECONDS = 10.0

_observer: Observer | None = None


class _PDFHandler(FileSystemEventHandler):
    """Handles new-file events in watched directories."""

    def __init__(self, category: str, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._category = category
        self._loop = loop
        self._pending: dict[str, asyncio.TimerHandle] = {}

    def _schedule(self, path: str) -> None:
        """Schedule ingestion after debounce window; cancels prior pending call."""
        if path in self._pending:
            self._pending[path].cancel()
        handle = self._loop.call_later(
            _DEBOUNCE_SECONDS,
            lambda: self._loop.create_task(_ingest_file(path, self._category)),
        )
        self._pending[path] = handle
        logger.debug("Scheduled ingest for %s in %.0fs", path, _DEBOUNCE_SECONDS)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            self._schedule(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            self._schedule(event.dest_path)


async def _ingest_file(path: str, category: str) -> None:
    """Extract text from *path* and ingest into RAG."""
    p = Path(path)
    if not p.exists():
        logger.warning("File disappeared before ingest: %s", path)
        return
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(p))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", path, exc)
        return

    if not text.strip():
        logger.warning("No text extracted from %s, skipping ingest", path)
        return

    try:
        from core.document_processor import ingest_text
        await ingest_text(text, source=p.name, category=category)
        logger.info("Auto-synced: %s (category=%s)", p.name, category)
    except Exception as exc:
        logger.warning("Ingest failed for %s: %s", path, exc)


def start_auto_sync(loop: asyncio.AbstractEventLoop) -> None:
    """Start the watchdog observer. Call from app lifespan after scheduler start."""
    global _observer
    if _observer is not None:
        return  # already running

    _observer = Observer()
    for watch_dir, category in _WATCH_DIRS:
        watch_dir.mkdir(parents=True, exist_ok=True)
        handler = _PDFHandler(category=category, loop=loop)
        _observer.schedule(handler, str(watch_dir), recursive=False)
        logger.info("Watching %s for new PDFs (category=%s)", watch_dir, category)

    _observer.start()
    logger.info("Auto-sync watchdog started")


def stop_auto_sync() -> None:
    """Stop the watchdog observer. Call from app lifespan shutdown."""
    global _observer
    if _observer is None:
        return
    _observer.stop()
    _observer.join()
    _observer = None
    logger.info("Auto-sync watchdog stopped")
