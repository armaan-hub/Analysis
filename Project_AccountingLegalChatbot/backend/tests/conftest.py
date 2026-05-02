"""
Pytest configuration and shared fixtures for the backend test suite.

ISOLATION: We set VECTOR_STORE_DIR and UPLOAD_DIR to temp directories BEFORE
importing the application, so ChromaDB and file uploads never touch production data.
See docs/superpowers/specs/SKILL.md §3 for the isolation spec.
"""
import os
import sys
import tempfile
from pathlib import Path

# --- Isolation: redirect vector store and uploads BEFORE app imports ---
_tmp_vector_store = tempfile.TemporaryDirectory(prefix="test_vector_store_")
_tmp_uploads      = tempfile.TemporaryDirectory(prefix="test_uploads_")

os.environ["VECTOR_STORE_DIR"] = _tmp_vector_store.name
os.environ["UPLOAD_DIR"]       = _tmp_uploads.name
# ----------------------------------------------------------------------

import asyncio
import pytest
import pytest_asyncio
import httpx
import respx
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app          # app import MUST come after env vars are set
from db.database import Base, get_db
from config import settings

# Fail-fast: assert that the vector store is NOT the real backend directory
_real_store = (Path(__file__).parent.parent / "vector_store_v2").resolve()
_test_store = Path(settings.vector_store_dir).resolve()
assert _test_store != _real_store, (
    f"conftest.py isolation failed! vector_store_dir still points at the real store: {_real_store}\n"
    "Check that VECTOR_STORE_DIR is set before 'from main import app'."
)


def pytest_sessionfinish(session, exitstatus):
    """Clean up temp directories after the full test session completes."""
    try:
        _tmp_vector_store.cleanup()
        _tmp_uploads.cleanup()
    except Exception:
        pass  # Best-effort cleanup; don't mask test failures


# ── In-memory test database ───────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_test_engine = create_async_engine(TEST_DB_URL, echo=False)
_test_session_factory = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# Sync session-scoped fixture: uses asyncio.run() for setup/teardown,
# completely sidestepping async fixture lifecycle issues on any
# pytest-asyncio version. The engine is module-level so later async
# fixtures reuse the same in-memory DB.
@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    async def _setup():
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest_asyncio.fixture()
async def db_session():
    async with _test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session):
    """HTTP test client that uses the in-memory test DB."""
    from contextlib import asynccontextmanager
    from unittest.mock import patch
    import respx
    import httpx

    async def override_get_db():
        yield db_session

    @asynccontextmanager
    async def _mock_session():
        yield db_session

    @asynccontextmanager
    async def _fresh_test_session():
        async with _test_session_factory() as session:
            yield session

    # Block all real API calls by default during tests to ensure isolation
    with respx.mock(assert_all_called=False) as respx_mock:
        # Mock embeddings to return a fake successful response
        def mock_embedding_side_effect(request):
            import json
            body = json.loads(request.content)
            inputs = body.get("input", [])
            # Return a fake 1024-dim embedding for each input
            embeddings = [[0.1] * 1024 for _ in inputs]
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": e, "index": i} for i, e in enumerate(embeddings)],
                    "model": body.get("model", "mock-model"),
                    "usage": {"prompt_tokens": 10, "total_tokens": 10}
                }
            )

        respx_mock.post("https://integrate.api.nvidia.com/v1/embeddings").mock(
            side_effect=mock_embedding_side_effect
        )

        # Also mock chat completions to avoid hitting the real API for chat
        respx_mock.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{
                        "message": {
                            "role": "assistant", 
                            "content": '{"summary": "Mock summary", "key_terms": ["term1", "term2"]}'
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
                }
            )
        )

        app.dependency_overrides[get_db] = override_get_db

        with patch("api.audit_studio.AsyncSessionLocal", _mock_session), \
             patch("core.audit_studio.versioning.AsyncSessionLocal", _mock_session), \
             patch("core.audit_studio.chat_service.AsyncSessionLocal", _mock_session), \
             patch("core.audit_studio.generation_service.AsyncSessionLocal", _mock_session), \
             patch("core.research.orchestrator.async_session", _mock_session), \
             patch("api.chat.AsyncSessionLocal", _fresh_test_session):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                yield ac
            # Drain any background tasks (e.g. _generate_title) while the session
            # factory patch is still active.  Without this, they run after the patch
            # exits and may corrupt the shared in-memory test DB connection.
            _cur = asyncio.current_task()
            _bg = [t for t in asyncio.all_tasks() if t is not _cur]
            if _bg:
                await asyncio.wait(_bg, timeout=1.0)

        app.dependency_overrides.clear()
