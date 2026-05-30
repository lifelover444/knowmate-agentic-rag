import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk, FAQEntry, Knowledge
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.faq import FAQEntryRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAIEmbedder
from app.schemas.faq import FAQEntryCreate, FAQEntryUpdate
from app.services.model_config import ModelConfigService


class FAQEntryService:
    def __init__(self, db: Session, settings: Settings, vector_store, embedder=None) -> None:
        self.db = db
        self.settings = settings
        self.vector_store = vector_store
        self.embedder = embedder
        self.repo = FAQEntryRepository(db)
        self.kb_repo = KnowledgeBaseRepository(db)
        self.chunks = ChunkRepository(db)

    def create(self, knowledge_base_id: str, payload: FAQEntryCreate) -> FAQEntry:
        kb = self._faq_kb(knowledge_base_id)
        entry_id = str(uuid.uuid4())
        entry = self.repo.create(
            FAQEntry(
                id=entry_id,
                tenant_id=self.settings.default_tenant_id,
                knowledge_base_id=kb.id,
                knowledge_id=entry_id,
                question=payload.question,
                answer=payload.answer,
                faq_metadata=payload.metadata or {},
                enabled=payload.enabled,
            )
        )
        self.rebuild_index(entry)
        return entry

    def update(self, entry: FAQEntry, payload: FAQEntryUpdate) -> FAQEntry:
        data = payload.model_dump(exclude_unset=True)
        if "question" in data and data["question"] is not None:
            entry.question = data["question"]
        if "answer" in data and data["answer"] is not None:
            entry.answer = data["answer"]
        if "metadata" in data:
            entry.faq_metadata = data["metadata"] or {}
        if "enabled" in data and data["enabled"] is not None:
            entry.enabled = data["enabled"]
        entry = self.repo.save(entry)
        self.rebuild_index(entry)
        return entry

    def delete(self, entry: FAQEntry) -> None:
        self.repo.soft_delete(entry)
        self._clear_index(entry)

    def rebuild_index(self, entry: FAQEntry) -> None:
        kb = self._faq_kb(entry.knowledge_base_id)
        self._clear_index(entry)
        knowledge = self.db.get(Knowledge, entry.knowledge_id)
        if knowledge is None:
            knowledge = Knowledge(
                id=entry.knowledge_id,
                tenant_id=entry.tenant_id,
                knowledge_base_id=entry.knowledge_base_id,
                type="faq",
                source_type="faq",
                title=entry.question,
                source="faq",
                parse_status="completed",
                enable_status="enabled" if entry.enabled else "disabled",
                file_size=0,
                storage_size=0,
                doc_metadata={"faq_entry_id": entry.id},
            )
        knowledge.title = entry.question
        knowledge.source_type = "faq"
        knowledge.type = "faq"
        knowledge.parse_status = "completed"
        knowledge.enable_status = "enabled" if entry.enabled else "disabled"
        knowledge.error_message = None
        self.db.add(knowledge)
        self.db.commit()
        if not entry.enabled:
            return

        content = _faq_content(entry)
        chunk = Chunk(
            id=str(uuid.uuid4()),
            tenant_id=entry.tenant_id,
            knowledge_base_id=entry.knowledge_base_id,
            knowledge_id=entry.knowledge_id,
            content=content,
            search_text=_faq_search_text(entry),
            chunk_index=0,
            is_enabled=True,
            start_at=0,
            end_at=len(content),
            chunk_type="faq",
            context_header="FAQ",
            chunk_metadata={
                **(entry.faq_metadata or {}),
                "title": entry.question,
                "faq_entry_id": entry.id,
                "source_type": "faq",
            },
            images=[],
        )
        self.chunks.replace_for_document(entry.knowledge_id, [chunk])
        embedder = self._embedder(kb.embedding_model_id)
        vectors = embedder.embed_many([content])
        self.vector_store.upsert_chunks(
            vectors=vectors,
            payloads=[
                {
                    "content": chunk.content,
                    "context_header": chunk.context_header,
                    "source_id": chunk.id,
                    "source_type": "faq",
                    "chunk_id": chunk.id,
                    "knowledge_id": entry.knowledge_id,
                    "knowledge_base_id": entry.knowledge_base_id,
                    "title": entry.question,
                    "is_enabled": True,
                    "parent_chunk_id": None,
                    "chunk_type": "faq",
                    "metadata": chunk.chunk_metadata or {},
                }
            ],
        )

    def _clear_index(self, entry: FAQEntry) -> None:
        if hasattr(self.vector_store, "delete_by_knowledge_id"):
            self.vector_store.delete_by_knowledge_id(entry.knowledge_id)
        self.chunks.replace_for_document(entry.knowledge_id, [])

    def _faq_kb(self, knowledge_base_id: str):
        kb = self.kb_repo.get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        if getattr(kb, "kb_type", "document") != "faq":
            raise ValueError("FAQ 条目只能创建在 FAQ 知识库中")
        return kb

    def _embedder(self, embedding_model_id: str):
        if self.embedder is not None:
            return self.embedder
        runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config_for_model(
            embedding_model_id,
            "Embedding",
        )
        return OpenAIEmbedder(runtime_config)


def _faq_content(entry: FAQEntry) -> str:
    return f"问题：{entry.question}\n答案：{entry.answer}"


def _faq_search_text(entry: FAQEntry) -> str:
    return "\n".join([entry.question, entry.answer]).strip()
