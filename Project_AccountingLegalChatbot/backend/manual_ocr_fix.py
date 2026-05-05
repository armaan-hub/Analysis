import asyncio
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so project imports resolve
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.database import Base
from db.models import Document
from core.rag_engine import rag_engine
from core.document_processor import DocumentChunk

_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"timeout": 60},
)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

TXT_DIR = Path("data/manual_ocr")

async def main() -> None:
    if not TXT_DIR.exists():
        print(f"Error: {TXT_DIR} not found.")
        return

    async with _session_factory() as db:
        files = list(TXT_DIR.glob("*.txt"))
        print(f"Found {len(files)} manual OCR text files.")

        for txt_path in files:
            # Map back to original PDF name
            original_name = txt_path.stem + ".pdf"
            print(f"Processing: {original_name}...")

            # Find existing Document record
            result = await db.execute(
                select(Document).where(Document.original_name == original_name)
            )
            doc = result.scalar_one_or_none()
            
            if not doc:
                print(f"  SKIP: Document record for {original_name} not found in DB.")
                continue

            # Update Document record
            content = txt_path.read_text(encoding="utf-8")
            doc.status = "indexed"  # type: ignore[assignment]
            doc.error_message = None  # type: ignore[assignment]
            
            # Index into RAG using the correct DocumentChunk class
            chunks = [DocumentChunk(
                text=content,
                metadata={
                    "doc_id": doc.id,
                    "source": original_name,
                    "page": "1",
                    "chunk_index": 0,
                    "category": doc.metadata_json.get("category", "unknown")
                }
            )]
            
            try:
                # Clear old chunks for this doc first if any exist
                await rag_engine.delete_document(str(doc.id))
                count = await rag_engine.ingest_chunks(chunks, str(doc.id))
                doc.chunk_count = count  # type: ignore[assignment]
                await db.commit()
                print(f"  OK: Indexed as '{original_name}' with {count} chunks.")
            except Exception as e:
                print(f"  ERR: Failed to index {original_name}: {e}")

    print("\nManual OCR fix completed.")

if __name__ == "__main__":
    asyncio.run(main())
