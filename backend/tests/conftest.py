"""
Pytest fixtures shared across all backend tests.
"""
import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from db.database import Base, get_db


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

    async def override_get_db():
        yield db_session

    @asynccontextmanager
    async def _mock_session():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with patch("api.audit_studio.AsyncSessionLocal", _mock_session), \
         patch("core.audit_studio.versioning.AsyncSessionLocal", _mock_session), \
         patch("core.audit_studio.chat_service.AsyncSessionLocal", _mock_session), \
         patch("core.audit_studio.generation_service.AsyncSessionLocal", _mock_session), \
         patch("core.research.orchestrator.async_session", _mock_session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()
