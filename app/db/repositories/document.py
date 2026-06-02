from datetime import UTC, datetime

from sqlalchemy import or_, select
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

    def get_including_deleted(self, document_id: str) -> Knowledge | None:
        return self.db.scalar(select(Knowledge).where(Knowledge.id == document_id))

    def find_active_by_file_hash(self, kb_id: str, file_hash: str) -> Knowledge | None:
        return self.db.scalar(
            select(Knowledge).where(
                Knowledge.knowledge_base_id == kb_id,
                Knowledge.file_hash == file_hash,
                Knowledge.deleted_at.is_(None),
            )
        )

    def list_by_knowledge_base(
        self,
        kb_id: str,
        *,
        status: str | None = None,
        file_type: str | None = None,
        keyword: str | None = None,
        tag_id: str | None = None,
    ) -> list[Knowledge]:
        query = select(Knowledge).where(Knowledge.knowledge_base_id == kb_id, Knowledge.deleted_at.is_(None))
        if status:
            query = query.where(Knowledge.parse_status == status)
        if file_type:
            query = query.where(Knowledge.file_type == file_type.lower().lstrip("."))
        if keyword:
            pattern = f"%{keyword}%"
            query = query.where(or_(Knowledge.title.ilike(pattern), Knowledge.file_name.ilike(pattern)))
        if tag_id:
            query = query.where(Knowledge.tag_id == tag_id)
        query = query.order_by(Knowledge.created_at.desc(), Knowledge.id.desc())
        return list(
            self.db.scalars(query).all()
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

    def move_to_knowledge_base(self, document: Knowledge, target_kb_id: str, embedding_model_id: str) -> Knowledge:
        document.knowledge_base_id = target_kb_id
        document.embedding_model_id = embedding_model_id
        document.tag_id = None
        chunks = list(self.db.scalars(select(Chunk).where(Chunk.knowledge_id == document.id)).all())
        for chunk in chunks:
            chunk.knowledge_base_id = target_kb_id
            chunk.tag_id = None
            self.db.add(chunk)
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document
