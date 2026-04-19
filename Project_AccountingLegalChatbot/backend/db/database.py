"""
Database connection and session management using SQLAlchemy async.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from config import settings


# Convert sqlite:/// to sqlite+aiosqlite:/// for async support
_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},
)

# Enable WAL mode on every new connection so concurrent reads don't block writes
from sqlalchemy import event
@event.listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db():
    """Create all tables on startup."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # SQLite's create_all won't add columns to existing tables.
    # Run ALTER TABLE manually, swallowing the error if the column already exists.
    async with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE templates ADD COLUMN format_family TEXT NOT NULL DEFAULT 'custom'",
            "ALTER TABLE templates ADD COLUMN format_variant TEXT",
            "ALTER TABLE documents ADD COLUMN summary TEXT",
            "ALTER TABLE documents ADD COLUMN key_terms JSON",
            "ALTER TABLE documents ADD COLUMN source TEXT DEFAULT 'upload'",
            "ALTER TABLE conversations ADD COLUMN domain TEXT",
            "ALTER TABLE conversations ADD COLUMN is_pinned BOOLEAN DEFAULT 0",
        ):
            try:
                await conn.execute(text(stmt))
            except OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise


async def get_db() -> AsyncSession:
    """FastAPI dependency – yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


AsyncSessionLocal = async_session
