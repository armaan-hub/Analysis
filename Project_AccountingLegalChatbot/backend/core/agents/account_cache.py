"""
Account-mapping cache backed by the app SQLite database.

Maps account_name → audit_category strings that were discovered either
from the CSV seed file or from LLM classification during trial balance
uploads.  The cache grows unboundedly — there is no hard limit on the
number of account names that can be stored.

Typical flow
------------
1. App startup: ``seed_from_csv`` loads the bundled CSV as starting data.
2. On each trial balance upload: ``lookup_many`` returns all known mappings.
3. Unknown accounts are classified by the LLM then saved via ``save_many``.
4. Subsequent uploads of the same company's TB skip the LLM entirely for
   accounts already in cache.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.database import async_session
from db.models import AccountMapping

logger = logging.getLogger(__name__)


def _norm(name: str) -> str:
    """Normalize an account name to a stable cache key."""
    return name.strip().lower()


async def lookup_many(account_names: list[str]) -> dict[str, str]:
    """
    Return ``{normalized_name: mapped_to}`` for any of *account_names*
    that are present in the cache.  Also increments hit_count for hits.
    """
    if not account_names:
        return {}
    keys = [_norm(n) for n in account_names]
    async with async_session() as session:
        result = await session.execute(
            select(AccountMapping.normalized_name, AccountMapping.mapped_to)
            .where(AccountMapping.normalized_name.in_(keys))
        )
        rows = result.fetchall()
        if rows:
            hit_keys = [r[0] for r in rows]
            await session.execute(
                update(AccountMapping)
                .where(AccountMapping.normalized_name.in_(hit_keys))
                .values(
                    hit_count=AccountMapping.hit_count + 1,
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
        return {r[0]: r[1] for r in rows}


async def save_many(
    mappings: list[tuple[str, str]],
    source: str = "llm",
) -> None:
    """
    Upsert ``[(display_name, mapped_to), ...]`` into the cache.

    On conflict (same normalized key): updates ``mapped_to``, ``source``,
    and ``last_seen_at`` — preserves the existing ``hit_count``.
    """
    if not mappings:
        return
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        for display_name, mapped_to in mappings:
            stmt = sqlite_insert(AccountMapping).values(
                normalized_name=_norm(display_name),
                display_name=display_name.strip(),
                mapped_to=mapped_to,
                source=source,
                hit_count=0,
                last_seen_at=now,
                created_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["normalized_name"],
                set_={
                    "mapped_to": stmt.excluded.mapped_to,
                    "source": stmt.excluded.source,
                    "last_seen_at": now,
                },
            )
            await session.execute(stmt)
        await session.commit()


async def seed_from_csv(csv_path: Path) -> int:
    """
    One-time seed from a CSV with columns ``account``, ``mapped_to``.

    Uses INSERT OR IGNORE — existing cache entries are never overwritten
    by the seed file, so real LLM-derived mappings take precedence.

    Returns the number of CSV rows processed.
    """
    mappings: list[tuple[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            account   = (row.get("account")   or "").strip()
            mapped_to = (row.get("mapped_to") or "").strip()
            if account and mapped_to:
                mappings.append((account, mapped_to))

    if not mappings:
        return 0

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        for display_name, mapped_to in mappings:
            stmt = sqlite_insert(AccountMapping).values(
                normalized_name=_norm(display_name),
                display_name=display_name,
                mapped_to=mapped_to,
                source="seed",
                hit_count=0,
                last_seen_at=now,
                created_at=now,
            ).on_conflict_do_nothing(index_elements=["normalized_name"])
            await session.execute(stmt)
        await session.commit()

    return len(mappings)


async def cache_size() -> int:
    """Return the total number of cached account mappings."""
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(AccountMapping)
        )
        return result.scalar() or 0
