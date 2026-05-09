"""Stage 0: Scan source directories and return files needing (re-)ingest."""
from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".docx"}


@dataclass
class PendingFile:
    path: str          # absolute path to the file
    source_dir: str    # "law" or "finance"
    sha256: str        # current hash of the file


class SourceScanner:
    """Compares source directories against a registry of known hashes.

    Args:
        source_law_dir: absolute path to law documents directory
        source_finance_dir: absolute path to finance documents directory
        registry: dict mapping file path → known SHA256 hash (from DB)
    """

    def __init__(
        self,
        source_law_dir: str,
        source_finance_dir: str,
        registry: dict[str, str],
    ) -> None:
        self._law_dir = source_law_dir
        self._finance_dir = source_finance_dir
        self._registry = registry

    def scan(self) -> list[PendingFile]:
        """Return all files that are new or changed vs. the registry."""
        pending: list[PendingFile] = []
        for source_label, dir_path in [("law", self._law_dir), ("finance", self._finance_dir)]:
            d = Path(dir_path)
            if not d.exists():
                logger.debug("Source dir does not exist, skipping: %s", dir_path)
                continue
            for fp in sorted(d.rglob("*")):
                if not fp.is_file():
                    continue
                if fp.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                    continue
                sha = _sha256(str(fp))
                known = self._registry.get(str(fp))
                if known != sha:
                    pending.append(PendingFile(path=str(fp), source_dir=source_label, sha256=sha))
        return pending


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def build_registry_from_db(db) -> dict[str, str]:
    """Load {file_path: content_hash} from Document rows with a source_dir set."""
    from sqlalchemy import select
    from db.models import Document
    result = await db.execute(
        select(Document.original_name, Document.content_hash, Document.source_dir)
        .where(Document.source_dir.isnot(None))
        .where(Document.content_hash.isnot(None))
    )
    # original_name is stored as the full path for source-dir documents
    return {row.original_name: row.content_hash for row in result.fetchall()}
