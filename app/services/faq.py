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
                similar_questions=_normalize_similar_questions(payload.question, payload.similar_questions),
                answer=payload.answer,
                faq_metadata=payload.metadata or {},
                tag_id=payload.tag_id,
                enabled=payload.enabled,
            )
        )
        self.rebuild_index(entry)
        return entry

    def update(self, entry: FAQEntry, payload: FAQEntryUpdate) -> FAQEntry:
        data = payload.model_dump(exclude_unset=True)
        if "question" in data and data["question"] is not None:
            entry.question = data["question"]
            entry.similar_questions = _normalize_similar_questions(entry.question, entry.similar_questions or [])
        if "similar_questions" in data and data["similar_questions"] is not None:
            entry.similar_questions = _normalize_similar_questions(entry.question, data["similar_questions"])
        if "answer" in data and data["answer"] is not None:
            entry.answer = data["answer"]
        if "metadata" in data:
            entry.faq_metadata = data["metadata"] or {}
        if "tag_id" in data:
            entry.tag_id = data["tag_id"]
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
        knowledge.tag_id = entry.tag_id
        knowledge.parse_status = "completed"
        knowledge.enable_status = "enabled" if entry.enabled else "disabled"
        knowledge.error_message = None
        self.db.add(knowledge)
        self.db.commit()
        if not entry.enabled:
            return

        chunks = [
            _to_faq_chunk(entry, item, index)
            for index, item in enumerate(_faq_index_items(entry, kb.faq_config))
        ]
        self.chunks.replace_for_document(entry.knowledge_id, chunks)
        embedder = self._embedder(kb.embedding_model_id)
        vectors = embedder.embed_many([chunk.search_text or chunk.content for chunk in chunks])
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
                    "tag_id": entry.tag_id,
                    "chunk_type": "faq",
                    "metadata": chunk.chunk_metadata or {},
                }
                for chunk in chunks
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


def _normalize_similar_questions(question: str, values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    standard = question.strip()
    for value in values or []:
        item = value.strip()
        if not item or item == standard or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _faq_index_config(config: dict | None) -> tuple[str, str]:
    data = config or {}
    index_mode = data.get("index_mode") or "question_answer"
    question_index_mode = data.get("question_index_mode") or "combined"
    return index_mode, question_index_mode


def _faq_index_items(entry: FAQEntry, config: dict | None) -> list[dict]:
    index_mode, question_index_mode = _faq_index_config(config)
    questions = [entry.question, *(entry.similar_questions or [])]
    if question_index_mode == "separate":
        return [
            _faq_index_item(
                entry,
                question=question,
                index_mode=index_mode,
                question_role="standard" if index == 0 else "similar",
            )
            for index, question in enumerate(questions)
        ]
    combined_question = "\n".join(questions)
    return [
        _faq_index_item(
            entry,
            question=combined_question,
            matched_question=entry.question,
            index_mode=index_mode,
            question_role="combined",
        )
    ]


def _faq_index_item(
    entry: FAQEntry,
    *,
    question: str,
    index_mode: str,
    question_role: str,
    matched_question: str | None = None,
) -> dict:
    content = question.strip()
    if index_mode == "question_answer":
        content = f"{content}\n{entry.answer}".strip()
    matched = matched_question or question.strip()
    metadata = {
        **(entry.faq_metadata or {}),
        "title": entry.question,
        "faq_entry_id": entry.id,
        "source_type": "faq",
        "standard_question": entry.question,
        "similar_questions": entry.similar_questions or [],
        "matched_question": matched,
        "question_role": question_role,
        "index_mode": index_mode,
    }
    return {"content": content, "search_text": content, "metadata": metadata}


def _to_faq_chunk(entry: FAQEntry, item: dict, index: int) -> Chunk:
    content = item["content"]
    return Chunk(
        id=str(uuid.uuid4()),
        tenant_id=entry.tenant_id,
        knowledge_base_id=entry.knowledge_base_id,
        knowledge_id=entry.knowledge_id,
        content=content,
        search_text=item["search_text"],
        chunk_index=index,
        is_enabled=True,
        start_at=0,
        end_at=len(content),
        chunk_type="faq",
        context_header="FAQ",
        tag_id=entry.tag_id,
        chunk_metadata=item["metadata"],
        images=[],
    )
