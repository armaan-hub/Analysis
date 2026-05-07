"""
Tests that UAE tenancy law documents are correctly stored and retrievable in ChromaDB.
These tests verify the state after Task 2 (document ingestion via upload API).

Run: pytest tests/test_tenancy_rag_retrieval.py -v
(Must be run from the backend/ directory with the correct venv active)
"""
import os
import pytest
import chromadb


VECTOR_STORE_PATH = os.path.expanduser("~/vector_store_v2")
TENANCY_DOC_NAMES = [
    "Dubai-Law-26-2007-Landlord-Tenant-Tenancy.txt",
    "Dubai-Law-33-2008-Tenancy-Amendment.txt",
    "RERA-Decree-43-2013-Rent-Increase-Tenancy-Guide.txt",
]


@pytest.fixture(scope="module")
def chroma_col():
    """Direct ChromaDB connection — works for metadata/keyword tests."""
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    return client.get_collection("documents")


class TestTenancyDocumentsIndexed:
    """Verify all three tenancy law documents are indexed in ChromaDB."""

    def test_total_chunks_above_baseline(self, chroma_col):
        """After ingestion, total chunk count must exceed 13,509 (pre-tenancy baseline)."""
        total = chroma_col.count()
        assert total > 13509, (
            f"Expected >13,509 chunks after tenancy ingestion, got {total}. "
            "Run Task 2 (upload via API) first."
        )

    def test_law_26_2007_indexed(self, chroma_col):
        """Dubai Law 26/2007 must have chunks in ChromaDB."""
        results = chroma_col.get(
            where={"original_name": "Dubai-Law-26-2007-Landlord-Tenant-Tenancy.txt"},
            limit=1,
            include=["metadatas"],
        )
        assert len(results["ids"]) > 0, (
            "Dubai-Law-26-2007 not found. Run Task 2 to upload via API."
        )

    def test_law_33_2008_indexed(self, chroma_col):
        """Dubai Law 33/2008 amendment must have chunks in ChromaDB."""
        results = chroma_col.get(
            where={"original_name": "Dubai-Law-33-2008-Tenancy-Amendment.txt"},
            limit=1,
            include=["metadatas"],
        )
        assert len(results["ids"]) > 0, (
            "Dubai-Law-33-2008 not found. Run Task 2 to upload via API."
        )

    def test_rera_decree_indexed(self, chroma_col):
        """RERA Decree 43/2013 must have chunks in ChromaDB."""
        results = chroma_col.get(
            where={"original_name": "RERA-Decree-43-2013-Rent-Increase-Tenancy-Guide.txt"},
            limit=1,
            include=["metadatas"],
        )
        assert len(results["ids"]) > 0, (
            "RERA-Decree-43-2013 not found. Run Task 2 to upload via API."
        )

    def test_all_tenancy_docs_have_general_domain(self, chroma_col):
        """All tenancy documents must be stored with domain='general'.
        This is critical: general_law queries search all domains (no filter),
        so general domain docs WILL surface. Finance domains would be filtered out.
        """
        for doc_name in TENANCY_DOC_NAMES:
            results = chroma_col.get(
                where={"original_name": doc_name},
                limit=5,
                include=["metadatas"],
            )
            if not results["ids"]:
                pytest.skip(f"{doc_name} not yet ingested")
            for meta in results["metadatas"]:
                domain = meta.get("domain", "")
                assert domain == "general", (
                    f"{doc_name} has domain='{domain}', expected 'general'. "
                    "Finance-domain docs would be suppressed for general_law queries."
                )

    def test_law_26_has_sufficient_chunks(self, chroma_col):
        """Law 26/2007 (10KB file) must produce at least 5 chunks."""
        results = chroma_col.get(
            where={"original_name": "Dubai-Law-26-2007-Landlord-Tenant-Tenancy.txt"},
            limit=50,
            include=["metadatas"],
        )
        assert len(results["ids"]) >= 5, (
            f"Expected >=5 chunks for Law 26/2007, got {len(results['ids'])}. "
            "File may not have been processed correctly."
        )


class TestTenancyContentQuality:
    """Verify tenancy chunks contain the expected legal content."""

    def test_law_26_contains_tenant_keyword(self, chroma_col):
        """Law 26/2007 chunks must contain the word 'Tenant'."""
        results = chroma_col.get(
            where={"original_name": "Dubai-Law-26-2007-Landlord-Tenant-Tenancy.txt"},
            where_document={"$contains": "Tenant"},
            limit=1,
            include=["documents"],
        )
        assert len(results["ids"]) > 0, (
            "No Law 26/2007 chunks contain 'Tenant'. Content may be malformed."
        )

    def test_law_33_contains_eviction_content(self, chroma_col):
        """Law 33/2008 chunks must contain eviction-related content."""
        results = chroma_col.get(
            where={"original_name": "Dubai-Law-33-2008-Tenancy-Amendment.txt"},
            where_document={"$contains": "eviction"},
            limit=1,
            include=["documents"],
        )
        # Try case-insensitive match
        if not results["ids"]:
            results = chroma_col.get(
                where={"original_name": "Dubai-Law-33-2008-Tenancy-Amendment.txt"},
                where_document={"$contains": "Eviction"},
                limit=1,
                include=["documents"],
            )
        assert len(results["ids"]) > 0, (
            "No Law 33/2008 chunks contain eviction-related content."
        )

    def test_rera_decree_contains_rent_increase_percentages(self, chroma_col):
        """RERA Decree chunks must contain rent increase percentage information."""
        results = chroma_col.get(
            where={"original_name": "RERA-Decree-43-2013-Rent-Increase-Tenancy-Guide.txt"},
            where_document={"$contains": "5%"},
            limit=1,
            include=["documents"],
        )
        assert len(results["ids"]) > 0, (
            "RERA Decree chunks do not contain '5%' rent increase data."
        )
