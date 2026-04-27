"""Tests for the auto-sync watchdog."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.pipeline.auto_sync import (
    _PDFHandler,
    _ingest_file,
    start_auto_sync,
    stop_auto_sync,
)


class TestPDFHandler:
    def test_non_pdf_file_not_scheduled(self):
        loop = asyncio.new_event_loop()
        handler = _PDFHandler(category="law", loop=loop)
        try:
            event = MagicMock()
            event.is_directory = False
            event.src_path = "/data/document.docx"
            with patch.object(handler, "_schedule") as mock_schedule:
                handler.on_created(event)
            mock_schedule.assert_not_called()
        finally:
            loop.close()

    def test_pdf_file_is_scheduled(self):
        loop = asyncio.new_event_loop()
        handler = _PDFHandler(category="law", loop=loop)
        try:
            event = MagicMock()
            event.is_directory = False
            event.src_path = "/data/vat_guide.pdf"
            with patch.object(handler, "_schedule") as mock_schedule:
                handler.on_created(event)
            mock_schedule.assert_called_once_with("/data/vat_guide.pdf")
        finally:
            loop.close()

    def test_debounce_cancels_prior_handle(self):
        loop = asyncio.new_event_loop()
        handler = _PDFHandler(category="law", loop=loop)
        try:
            mock_handle = MagicMock()
            handler._pending["/data/file.pdf"] = mock_handle
            callbacks: list = []
            with patch.object(loop, "call_soon_threadsafe", side_effect=lambda cb: callbacks.append(cb)):
                with patch.object(loop, "call_later", return_value=MagicMock()):
                    handler._schedule("/data/file.pdf")
            # Invoke the callback as the event loop would
            for cb in callbacks:
                cb()
            mock_handle.cancel.assert_called_once()
        finally:
            loop.close()

    def test_moved_pdf_is_scheduled(self):
        loop = asyncio.new_event_loop()
        handler = _PDFHandler(category="finance", loop=loop)
        try:
            event = MagicMock()
            event.is_directory = False
            event.dest_path = "/data/report.pdf"
            with patch.object(handler, "_schedule") as mock_schedule:
                handler.on_moved(event)
            mock_schedule.assert_called_once_with("/data/report.pdf")
        finally:
            loop.close()

    def test_schedule_uses_call_soon_threadsafe(self):
        """_schedule must use call_soon_threadsafe, not call_later directly (thread safety)."""
        loop = asyncio.new_event_loop()
        handler = _PDFHandler(category="law", loop=loop)
        try:
            with patch.object(loop, "call_soon_threadsafe") as mock_threadsafe:
                handler._schedule("/data/vat_guide.pdf")
            mock_threadsafe.assert_called_once()
        finally:
            loop.close()


class TestIngestFile:
    async def test_missing_file_logs_warning_and_returns(self, tmp_path):
        missing = str(tmp_path / "nonexistent.pdf")
        # Should not raise, just log warning
        await _ingest_file(missing, "law")

    async def test_successful_ingest(self, tmp_path):
        import fitz
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "VAT on hotel apartments")
        doc.save(str(pdf_path))
        doc.close()

        with patch("core.document_processor.ingest_text", new=AsyncMock()) as mock_ingest:
            await _ingest_file(str(pdf_path), "law")
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args
        assert call_kwargs.kwargs.get("category") == "law"


class TestStartStopAutoSync:
    def test_start_creates_observer(self):
        loop = asyncio.new_event_loop()
        try:
            with patch("core.pipeline.auto_sync.Observer") as MockObserver:
                mock_obs = MagicMock()
                MockObserver.return_value = mock_obs
                start_auto_sync(loop)
                mock_obs.start.assert_called_once()
                stop_auto_sync()
        finally:
            loop.close()

    def test_stop_joins_observer(self):
        loop = asyncio.new_event_loop()
        try:
            with patch("core.pipeline.auto_sync.Observer") as MockObserver:
                mock_obs = MagicMock()
                MockObserver.return_value = mock_obs
                start_auto_sync(loop)
                stop_auto_sync()
                mock_obs.stop.assert_called_once()
                mock_obs.join.assert_called_once()
        finally:
            loop.close()

    def test_double_start_is_idempotent(self):
        loop = asyncio.new_event_loop()
        try:
            with patch("core.pipeline.auto_sync.Observer") as MockObserver:
                mock_obs = MagicMock()
                MockObserver.return_value = mock_obs
                start_auto_sync(loop)
                start_auto_sync(loop)  # second call must be a no-op
                assert MockObserver.call_count == 1
                stop_auto_sync()
        finally:
            loop.close()
