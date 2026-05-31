from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Knowledge, KnowledgeTag


class KnowledgeTagRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, tag: KnowledgeTag) -> KnowledgeTag:
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def save(self, tag: KnowledgeTag) -> KnowledgeTag:
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def get(self, tag_id: str, tenant_id: int | None = None) -> KnowledgeTag | None:
        query = select(KnowledgeTag).where(KnowledgeTag.id == tag_id)
        if tenant_id is not None:
            query = query.where(KnowledgeTag.tenant_id == tenant_id)
        return self.db.scalar(query)

    def get_by_name(self, *, tenant_id: int, knowledge_base_id: str, name: str) -> KnowledgeTag | None:
        return self.db.scalar(
            select(KnowledgeTag).where(
                KnowledgeTag.tenant_id == tenant_id,
                KnowledgeTag.knowledge_base_id == knowledge_base_id,
                KnowledgeTag.name == name,
            )
        )

    def list_by_knowledge_base(
        self,
        *,
        tenant_id: int,
        knowledge_base_id: str,
        keyword: str | None = None,
    ) -> list[KnowledgeTag]:
        query = select(KnowledgeTag).where(
            KnowledgeTag.tenant_id == tenant_id,
            KnowledgeTag.knowledge_base_id == knowledge_base_id,
        )
        if keyword:
            query = query.where(KnowledgeTag.name.ilike(f"%{keyword}%"))
        query = query.order_by(KnowledgeTag.sort_order.asc(), KnowledgeTag.created_at.desc(), KnowledgeTag.id.desc())
        return list(self.db.scalars(query).all())

    def reference_counts(self, *, tenant_id: int, knowledge_base_id: str, tag_id: str) -> tuple[int, int]:
        knowledge_count = self.db.scalar(
            select(func.count())
            .select_from(Knowledge)
            .where(
                Knowledge.tenant_id == tenant_id,
                Knowledge.knowledge_base_id == knowledge_base_id,
                Knowledge.tag_id == tag_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        chunk_count = self.db.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(
                Chunk.tenant_id == tenant_id,
                Chunk.knowledge_base_id == knowledge_base_id,
                Chunk.tag_id == tag_id,
                Chunk.deleted_at.is_(None),
            )
        )
        return int(knowledge_count or 0), int(chunk_count or 0)

    def delete(self, tag: KnowledgeTag) -> None:
        self.db.delete(tag)
        self.db.commit()
