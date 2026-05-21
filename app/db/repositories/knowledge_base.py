from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Knowledge, KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, kb: KnowledgeBase) -> KnowledgeBase:
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def get(self, kb_id: str, tenant_id: int) -> KnowledgeBase | None:
        return self.db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.deleted_at.is_(None),
            )
        )

    def counts(self, kb_id: str) -> tuple[int, int, int]:
        document_count = (
            self.db.scalar(select(func.count(Knowledge.id)).where(Knowledge.knowledge_base_id == kb_id)) or 0
        )
        chunk_count = self.db.scalar(select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == kb_id)) or 0
        processing_count = (
            self.db.scalar(
                select(func.count(Knowledge.id)).where(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.parse_status.in_(("pending", "processing")),
                )
            )
            or 0
        )
        return int(document_count), int(chunk_count), int(processing_count)
