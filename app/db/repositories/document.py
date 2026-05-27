from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Knowledge


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: Knowledge) -> Knowledge:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get(self, document_id: str) -> Knowledge | None:
        return self.db.scalar(select(Knowledge).where(Knowledge.id == document_id, Knowledge.deleted_at.is_(None)))

    def list_by_knowledge_base(self, kb_id: str) -> list[Knowledge]:
        return list(
            self.db.scalars(
                select(Knowledge)
                .where(Knowledge.knowledge_base_id == kb_id, Knowledge.deleted_at.is_(None))
                .order_by(Knowledge.created_at.desc(), Knowledge.id.desc())
            ).all()
        )

    def save(self, document: Knowledge) -> Knowledge:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def soft_delete(self, document: Knowledge) -> Knowledge:
        now = datetime.now(UTC)
        document.deleted_at = now
        document.enable_status = "disabled"
        chunks = list(self.db.scalars(select(Chunk).where(Chunk.knowledge_id == document.id)).all())
        for chunk in chunks:
            chunk.deleted_at = now
            chunk.is_enabled = False
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def soft_delete_by_knowledge_base(self, kb_id: str) -> list[Knowledge]:
        documents = list(self.db.scalars(select(Knowledge).where(Knowledge.knowledge_base_id == kb_id)).all())
        now = datetime.now(UTC)
        for document in documents:
            document.deleted_at = document.deleted_at or now
            document.enable_status = "disabled"
        chunks = list(self.db.scalars(select(Chunk).where(Chunk.knowledge_base_id == kb_id)).all())
        for chunk in chunks:
            chunk.deleted_at = chunk.deleted_at or now
            chunk.is_enabled = False
        self.db.commit()
        return documents
