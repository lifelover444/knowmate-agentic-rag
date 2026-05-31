from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk, FAQEntry, Knowledge, KnowledgeTag
from app.db.repositories.faq import FAQEntryRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.tag import KnowledgeTagRepository
from app.schemas.tags import TagCreate, TagRead, TagUpdate
from app.services.faq import FAQEntryService


class KnowledgeTagService:
    def __init__(self, db: Session, settings: Settings, vector_store=None, embedder=None) -> None:
        self.db = db
        self.settings = settings
        self.vector_store = vector_store
        self.embedder = embedder
        self.repo = KnowledgeTagRepository(db)
        self.kb_repo = KnowledgeBaseRepository(db)

    def list_tags(self, knowledge_base_id: str, *, keyword: str | None = None) -> list[TagRead]:
        kb = self._knowledge_base(knowledge_base_id)
        tags = self.repo.list_by_knowledge_base(
            tenant_id=kb.tenant_id,
            knowledge_base_id=kb.id,
            keyword=(keyword or "").strip() or None,
        )
        return [self.to_read(tag) for tag in tags]

    def create_tag(self, knowledge_base_id: str, payload: TagCreate) -> TagRead:
        kb = self._knowledge_base(knowledge_base_id)
        name = payload.name.strip()
        if not name:
            raise ValueError("标签名称不能为空")
        if self.repo.get_by_name(tenant_id=kb.tenant_id, knowledge_base_id=kb.id, name=name) is not None:
            raise FileExistsError("标签名称已存在")
        tag = self.repo.create(
            KnowledgeTag(
                tenant_id=kb.tenant_id,
                knowledge_base_id=kb.id,
                name=name,
                color=(payload.color or "").strip() or None,
                sort_order=payload.sort_order,
            )
        )
        return self.to_read(tag)

    def update_tag(self, knowledge_base_id: str, tag_id: str, payload: TagUpdate) -> TagRead:
        kb = self._knowledge_base(knowledge_base_id)
        tag = self._tag(kb.id, tag_id)
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            name = data["name"].strip()
            if not name:
                raise ValueError("标签名称不能为空")
            existing = self.repo.get_by_name(tenant_id=kb.tenant_id, knowledge_base_id=kb.id, name=name)
            if existing is not None and existing.id != tag.id:
                raise FileExistsError("标签名称已存在")
            tag.name = name
        if "color" in data:
            tag.color = (data["color"] or "").strip() or None
        if "sort_order" in data and data["sort_order"] is not None:
            tag.sort_order = data["sort_order"]
        tag.updated_at = datetime.now(UTC)
        return self.to_read(self.repo.save(tag))

    def delete_tag(self, knowledge_base_id: str, tag_id: str) -> None:
        kb = self._knowledge_base(knowledge_base_id)
        tag = self._tag(kb.id, tag_id)
        knowledge_count, chunk_count = self.repo.reference_counts(
            tenant_id=kb.tenant_id,
            knowledge_base_id=kb.id,
            tag_id=tag.id,
        )
        if knowledge_count or chunk_count:
            raise ValueError("标签仍有文档或 FAQ 引用，无法删除")
        self.repo.delete(tag)

    def assign_documents(self, knowledge_base_id: str, updates: dict[str, str | None]) -> int:
        kb = self._knowledge_base(knowledge_base_id)
        normalized = {document_id: self._validated_tag_id(kb.id, tag_id) for document_id, tag_id in updates.items()}
        updated = 0
        for document_id, tag_id in normalized.items():
            document = self.db.scalar(
                select(Knowledge).where(
                    Knowledge.id == document_id,
                    Knowledge.tenant_id == kb.tenant_id,
                    Knowledge.knowledge_base_id == kb.id,
                    Knowledge.deleted_at.is_(None),
                )
            )
            if document is None:
                continue
            document.tag_id = tag_id
            self.db.query(Chunk).filter(
                Chunk.tenant_id == kb.tenant_id,
                Chunk.knowledge_base_id == kb.id,
                Chunk.knowledge_id == document.id,
            ).update({"tag_id": tag_id}, synchronize_session=False)
            updated += 1
        self.db.commit()
        if self.vector_store is not None and hasattr(self.vector_store, "set_tag_for_knowledge_ids"):
            by_tag: dict[str | None, list[str]] = {}
            for document_id, tag_id in normalized.items():
                by_tag.setdefault(tag_id, []).append(document_id)
            for tag_id, knowledge_ids in by_tag.items():
                self.vector_store.set_tag_for_knowledge_ids(knowledge_ids=knowledge_ids, tag_id=tag_id)
        return updated

    def assign_faqs(self, knowledge_base_id: str, updates: dict[str, str | None]) -> int:
        kb = self._knowledge_base(knowledge_base_id)
        if getattr(kb, "kb_type", "document") != "faq":
            raise ValueError("FAQ 标签只能用于 FAQ 知识库")
        normalized = {faq_id: self._validated_tag_id(kb.id, tag_id) for faq_id, tag_id in updates.items()}
        updated_entries: list[FAQEntry] = []
        for faq_id, tag_id in normalized.items():
            entry = FAQEntryRepository(self.db).get(faq_id, kb.tenant_id)
            if entry is None or entry.knowledge_base_id != kb.id:
                continue
            entry.tag_id = tag_id
            knowledge = self.db.get(Knowledge, entry.knowledge_id)
            if knowledge is not None:
                knowledge.tag_id = tag_id
            updated_entries.append(entry)
        self.db.commit()
        faq_service = FAQEntryService(self.db, self.settings, self.vector_store, embedder=self.embedder)
        for entry in updated_entries:
            faq_service.rebuild_index(entry)
        return len(updated_entries)

    def to_read(self, tag: KnowledgeTag) -> TagRead:
        knowledge_count, chunk_count = self.repo.reference_counts(
            tenant_id=tag.tenant_id,
            knowledge_base_id=tag.knowledge_base_id,
            tag_id=tag.id,
        )
        return TagRead.model_validate(
            {
                **tag.__dict__,
                "knowledge_count": knowledge_count,
                "chunk_count": chunk_count,
            }
        )

    def _knowledge_base(self, knowledge_base_id: str):
        kb = self.kb_repo.get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        return kb

    def _tag(self, knowledge_base_id: str, tag_id: str) -> KnowledgeTag:
        tag = self.repo.get(tag_id, self.settings.default_tenant_id)
        if tag is None or tag.knowledge_base_id != knowledge_base_id:
            raise LookupError("标签不存在")
        return tag

    def _validated_tag_id(self, knowledge_base_id: str, tag_id: str | None) -> str | None:
        if tag_id is None:
            return None
        return self._tag(knowledge_base_id, tag_id).id
