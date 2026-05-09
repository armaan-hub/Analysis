"""Entity knowledge graph backed by SQLite (aiosqlite).

Public API:
    EntityGraph(db_path: str)
        .init() -> None
        .store_entities(doc_id, entities, relationships) -> None
        .search_entities(query: str, limit: int) -> list[dict]
        .parse_llm_response(raw: str) -> tuple[list[Entity], list[Relationship]]
        .delete_by_doc(doc_id: str) -> None
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name:       str
    type:       str
    properties: dict = field(default_factory=dict)


@dataclass
class Relationship:
    source_name:  str
    target_name:  str
    relationship: str


_CREATE_ENTITIES = """
CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     TEXT NOT NULL,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL,
    properties TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)"""

_CREATE_RELATIONSHIPS = """
CREATE TABLE IF NOT EXISTS relationships (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL,
    target_id    INTEGER NOT NULL,
    relationship TEXT NOT NULL,
    doc_id       TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES entities(id),
    FOREIGN KEY (target_id) REFERENCES entities(id)
)"""


class EntityGraph:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_ENTITIES)
            await db.execute(_CREATE_RELATIONSHIPS)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_doc_id ON entities(doc_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name COLLATE NOCASE)")
            await db.commit()

    async def store_entities(self, doc_id: str, entities: list[Entity], relationships: list[Relationship]) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            name_to_id: dict[str, int] = {}
            for ent in entities:
                cur = await db.execute(
                    "INSERT INTO entities (doc_id, name, type, properties) VALUES (?, ?, ?, ?)",
                    (doc_id, ent.name, ent.type, json.dumps(ent.properties)),
                )
                name_to_id[ent.name] = cur.lastrowid
            for rel in relationships:
                src_id = name_to_id.get(rel.source_name)
                tgt_id = name_to_id.get(rel.target_name)
                if src_id and tgt_id:
                    await db.execute(
                        "INSERT INTO relationships (source_id, target_id, relationship, doc_id) VALUES (?, ?, ?, ?)",
                        (src_id, tgt_id, rel.relationship, doc_id),
                    )
            await db.commit()

    async def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        pattern = f"%{query}%"
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, doc_id, name, type, properties FROM entities WHERE name LIKE ? COLLATE NOCASE LIMIT ?",
                (pattern, limit),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    def parse_llm_response(self, raw: str) -> tuple[list[Entity], list[Relationship]]:
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            entities = [Entity(name=e["name"], type=e.get("type", "concept"), properties=e.get("properties", {})) for e in data.get("entities", [])]
            relationships = [Relationship(source_name=r["source"], target_name=r["target"], relationship=r.get("relationship", "related_to")) for r in data.get("relationships", [])]
            return entities, relationships
        except Exception as exc:
            logger.debug("parse_llm_response failed: %s", exc)
            return [], []

    async def delete_by_doc(self, doc_id: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute("SELECT id FROM entities WHERE doc_id=?", (doc_id,))
            ids = [row[0] for row in await cur.fetchall()]
            if ids:
                placeholders = ",".join("?" * len(ids))
                await db.execute(f"DELETE FROM relationships WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})", ids + ids)
            await db.execute("DELETE FROM entities WHERE doc_id=?", (doc_id,))
            await db.commit()
