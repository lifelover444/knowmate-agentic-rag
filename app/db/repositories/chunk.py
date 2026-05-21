from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Chunk


class ChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_for_document(self, knowledge_id: str, chunks: list[Chunk]) -> list[Chunk]:
        self.db.execute(delete(Chunk).where(Chunk.knowledge_id == knowledge_id))
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def list_by_document(self, knowledge_id: str) -> list[Chunk]:
        return list(
            self.db.scalars(
                select(Chunk).where(Chunk.knowledge_id == knowledge_id).order_by(Chunk.chunk_index.asc())
            ).all()
        )
