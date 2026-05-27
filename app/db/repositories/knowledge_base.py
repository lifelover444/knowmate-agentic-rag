from datetime import UTC, datetime

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

    def list(self, tenant_id: int) -> list[KnowledgeBase]:
        return list(
            self.db.scalars(
                select(KnowledgeBase)
                .where(KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.deleted_at.is_(None))
                .order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc())
            ).all()
        )

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
            self.db.scalar(
                select(func.count(Knowledge.id)).where(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.deleted_at.is_(None),
                )
            )
            or 0
        )
        chunk_count = (
            self.db.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.knowledge_base_id == kb_id,
                    Chunk.deleted_at.is_(None),
                )
            )
            or 0
        )
        processing_count = (
            self.db.scalar(
                select(func.count(Knowledge.id)).where(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.deleted_at.is_(None),
                    Knowledge.parse_status.in_(("pending", "processing")),
                )
            )
            or 0
        )
        return int(document_count), int(chunk_count), int(processing_count)

    def save(self, kb: KnowledgeBase) -> KnowledgeBase:
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def soft_delete(self, kb: KnowledgeBase) -> KnowledgeBase:
        kb.deleted_at = datetime.now(UTC)
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb
