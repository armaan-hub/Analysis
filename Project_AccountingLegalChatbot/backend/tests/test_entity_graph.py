import pytest
import aiosqlite


@pytest.fixture
def tmp_graph_db(tmp_path):
    return str(tmp_path / "test_entity_graph.db")


@pytest.mark.asyncio
async def test_entity_graph_init_creates_tables(tmp_graph_db):
    from core.entity_graph import EntityGraph
    g = EntityGraph(tmp_graph_db)
    await g.init()
    async with aiosqlite.connect(tmp_graph_db) as db:
        cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] async for row in cur}
    assert "entities" in tables
    assert "relationships" in tables


@pytest.mark.asyncio
async def test_entity_graph_store_and_retrieve(tmp_graph_db):
    from core.entity_graph import EntityGraph, Entity, Relationship
    g = EntityGraph(tmp_graph_db)
    await g.init()
    entities = [
        Entity(name="Article 15", type="article", properties={"number": 15}),
        Entity(name="Decree Law 50/2022", type="law", properties={"effective_date": "2022-09-01"}),
    ]
    relationships = [Relationship(source_name="Article 15", target_name="Decree Law 50/2022", relationship="part_of")]
    await g.store_entities("doc-001", entities, relationships)
    async with aiosqlite.connect(tmp_graph_db) as db:
        cur = await db.execute("SELECT COUNT(*) FROM entities WHERE doc_id=?", ("doc-001",))
        row = await cur.fetchone()
    assert row[0] == 2


@pytest.mark.asyncio
async def test_entity_graph_search_by_name(tmp_graph_db):
    from core.entity_graph import EntityGraph, Entity
    g = EntityGraph(tmp_graph_db)
    await g.init()
    await g.store_entities("doc-001", [Entity(name="Bounced Cheque Penalties", type="concept", properties={})], [])
    results = await g.search_entities("bounced cheque")
    assert any("Bounced" in r["name"] for r in results)


@pytest.mark.asyncio
async def test_extract_entities_from_llm_response_valid_json():
    from core.entity_graph import EntityGraph
    import json
    g = EntityGraph(":memory:")
    raw = json.dumps({
        "entities": [{"name": "Article 15", "type": "article", "properties": {"number": 15}}],
        "relationships": [{"source": "Article 15", "target": "Decree Law 50/2022", "relationship": "part_of"}],
    })
    entities, rels = g.parse_llm_response(raw)
    assert len(entities) == 1
    assert entities[0].name == "Article 15"
    assert len(rels) == 1
    assert rels[0].relationship == "part_of"


@pytest.mark.asyncio
async def test_extract_entities_from_llm_response_invalid_json():
    from core.entity_graph import EntityGraph
    g = EntityGraph(":memory:")
    entities, rels = g.parse_llm_response("not json at all")
    assert entities == []
    assert rels == []
