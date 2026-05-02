"""
Document category tagging tests — verifies studio→category mapping and ChromaDB storage.

TDD spec: Documents uploaded from Legal Studio should be tagged category="law"
in ChromaDB chunks so the RAG filter {"category": "law"} returns them.
"""
import io
import uuid
import pytest
from core.document_processor import DocumentChunk
from core.rag_engine import rag_engine


@pytest.mark.asyncio
async def test_upload_legal_studio_sets_law_category(client):
    """Upload with studio="legal" → chunks should have category="law" in ChromaDB."""
    content = b"UAE contract inheritance estate " + str(uuid.uuid4()).encode() + b" about obligations and liability."
    
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("legal_doc.txt", io.BytesIO(content), "text/plain")},
        data={"studio": "legal"},
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["status"] == "indexed"
    doc_id = doc["id"]
    
    # Query ChromaDB directly to verify category metadata
    results = rag_engine.collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )
    
    assert len(results["ids"]) > 0, "No chunks found in ChromaDB"
    for meta in results["metadatas"]:
        assert "category" in meta, f"Missing 'category' in chunk metadata: {meta}"
        assert meta["category"] == "law", f"Expected category='law', got {meta['category']}"


@pytest.mark.asyncio
async def test_upload_analyst_sets_finance_category(client):
    """Upload with studio="analyst" → chunks should have category="finance"."""
    content = b"Financial report " + str(uuid.uuid4()).encode() + b" about revenue analysis."
    
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("finance_doc.txt", io.BytesIO(content), "text/plain")},
        data={"studio": "analyst"},
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["status"] == "indexed"
    doc_id = doc["id"]
    
    results = rag_engine.collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )
    
    assert len(results["ids"]) > 0
    for meta in results["metadatas"]:
        assert "category" in meta
        assert meta["category"] == "finance", f"Expected category='finance', got {meta['category']}"


@pytest.mark.asyncio
async def test_upload_no_studio_sets_general_category(client):
    """Upload without studio param → chunks should have category="general"."""
    content = b"Generic document contract " + str(uuid.uuid4()).encode() + b" without studio tag obligations."
    
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("generic_doc.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["status"] == "indexed"
    doc_id = doc["id"]
    
    results = rag_engine.collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )
    
    assert len(results["ids"]) > 0
    for meta in results["metadatas"]:
        assert "category" in meta
        assert meta["category"] == "general", f"Expected category='general', got {meta['category']}"


@pytest.mark.asyncio
async def test_ingest_chunks_stores_category():
    """Unit test — ingest_chunks with category param stores it in ChromaDB."""
    # Create test chunks
    doc_id = f"test_doc_{uuid.uuid4()}"
    chunks = [
        DocumentChunk(
            text=f"In the matter of Federal Decree No. 37, the Ministry of Justice in Dubai has issued guidelines regarding inheritance and wills under UAE law. Chunk {i}.",
            metadata={"page": i, "source": "test.txt"}
        )
        for i in range(3)
    ]
    
    # Ingest with category="law"
    count = await rag_engine.ingest_chunks(
        chunks,
        doc_id=doc_id,
        original_name="test.txt",
        category="law"
    )
    
    assert count == 3, f"Expected 3 chunks ingested, got {count}"
    
    # Verify category is stored in ChromaDB
    results = rag_engine.collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )
    
    assert len(results["ids"]) == 3
    for meta in results["metadatas"]:
        assert "category" in meta
        assert meta["category"] == "law"
        assert meta["doc_id"] == doc_id
        assert meta["original_name"] == "test.txt"


@pytest.mark.asyncio
async def test_category_filter_isolation(client):
    """Verify category filter actually isolates documents by category."""
    # Upload legal doc
    legal_content = b"Legal contract inheritance estate " + str(uuid.uuid4()).encode()
    resp1 = await client.post(
        "/api/documents/upload",
        files={"file": ("legal.txt", io.BytesIO(legal_content), "text/plain")},
        data={"studio": "legal"},
    )
    legal_doc_id = resp1.json()["document"]["id"]
    
    # Upload finance doc
    finance_content = b"Finance revenue dividend " + str(uuid.uuid4()).encode()
    resp2 = await client.post(
        "/api/documents/upload",
        files={"file": ("finance.txt", io.BytesIO(finance_content), "text/plain")},
        data={"studio": "analyst"},
    )
    finance_doc_id = resp2.json()["document"]["id"]
    
    # Query with category filter for "law" — should only return legal doc
    law_results = rag_engine.collection.get(
        where={"category": "law"},
        include=["metadatas"],
    )
    law_doc_ids = {meta["doc_id"] for meta in law_results["metadatas"]}
    assert legal_doc_id in law_doc_ids
    assert finance_doc_id not in law_doc_ids
    
    # Query with category filter for "finance" — should only return finance doc
    finance_results = rag_engine.collection.get(
        where={"category": "finance"},
        include=["metadatas"],
    )
    finance_doc_ids = {meta["doc_id"] for meta in finance_results["metadatas"]}
    assert finance_doc_id in finance_doc_ids
    assert legal_doc_id not in finance_doc_ids


@pytest.mark.asyncio
async def test_upload_finance_studio_sets_finance_category(client):
    """Upload with studio="finance" → chunks should have category="finance"."""
    content = b"Finance studio document " + str(uuid.uuid4()).encode() + b" balance sheet data."

    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("balance.txt", io.BytesIO(content), "text/plain")},
        data={"studio": "finance"},
    )
    assert resp.status_code == 200
    doc = resp.json()["document"]
    assert doc["status"] == "indexed"
    doc_id = doc["id"]

    results = rag_engine.collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )

    assert len(results["ids"]) > 0
    for meta in results["metadatas"]:
        assert "category" in meta
        assert meta["category"] == "finance", f"Expected category='finance', got {meta['category']}"


@pytest.mark.asyncio
async def test_dedup_retags_chunks_when_studio_changes(client):
    """If the same file is re-uploaded with a different studio, chunks are re-tagged."""
    unique_content = b"Dedup re-tag contract inheritance test " + str(uuid.uuid4()).encode() + b" obligations liability here."

    # First upload: no studio → category="general"
    resp1 = await client.post(
        "/api/documents/upload",
        files={"file": ("contract.txt", io.BytesIO(unique_content), "text/plain")},
    )
    assert resp1.status_code == 200
    doc_id = resp1.json()["document"]["id"]

    # Verify initial category is "general"
    result = rag_engine.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
    for meta in result["metadatas"]:
        assert meta["category"] == "general"

    # Second upload: same file with studio="legal" → should re-tag to category="law"
    resp2 = await client.post(
        "/api/documents/upload",
        files={"file": ("contract.txt", io.BytesIO(unique_content), "text/plain")},
        data={"studio": "legal"},
    )
    assert resp2.status_code == 200
    # Dedup returns same doc id
    assert resp2.json()["document"]["id"] == doc_id

    # Verify category is now "law"
    result2 = rag_engine.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
    assert len(result2["ids"]) > 0
    for meta in result2["metadatas"]:
        assert meta["category"] == "law", f"Expected re-tagged category='law', got {meta['category']}"
