import uuid
from datetime import UTC, datetime

from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.schemas.chunk import ChunkUpdateRequest


class ChunkService:
    def __init__(self, repo: ChunkRepository, vector_store=None) -> None:
        self.repo = repo
        self.vector_store = vector_store

    def get_by_id(self, chunk_id: str) -> Chunk:
        chunk = self.repo.get(chunk_id)
        if chunk is None:
            raise LookupError("Chunk 不存在")
        return chunk

    def update(self, knowledge_id: str, chunk_id: str, payload: ChunkUpdateRequest) -> tuple[Chunk, bool]:
        chunk = self.get_by_id(chunk_id)
        if chunk.knowledge_id != knowledge_id:
            raise PermissionError("Chunk 不属于当前文档")

        data = payload.model_dump(exclude_unset=True)
        requires_reindex = False
        vector_payload: dict = {}
        if "content" in data and data["content"] is not None:
            chunk.content = data["content"]
            chunk.end_at = chunk.start_at + len(chunk.content)
            vector_payload["content"] = chunk.content
            requires_reindex = True
        if "search_text" in data:
            chunk.search_text = data["search_text"]
            requires_reindex = True
        if "metadata" in data:
            chunk.chunk_metadata = data["metadata"] or {}
            vector_payload["metadata"] = chunk.chunk_metadata
        if "is_enabled" in data and data["is_enabled"] is not None:
            chunk.is_enabled = data["is_enabled"]
            vector_payload["is_enabled"] = chunk.is_enabled
        chunk.updated_at = datetime.now(UTC)
        chunk = self.repo.save(chunk)
        self._sync_vector_payload(chunk, vector_payload)
        return chunk, requires_reindex

    def disable(self, knowledge_id: str, chunk_id: str) -> Chunk:
        chunk = self.get_by_id(chunk_id)
        if chunk.knowledge_id != knowledge_id:
            raise PermissionError("Chunk 不属于当前文档")
        chunk = self.repo.soft_delete(chunk)
        self._sync_vector_payload(chunk, {"is_enabled": False})
        return chunk

    def add_generated_question(self, chunk_id: str, question: str) -> Chunk:
        chunk = self.get_by_id(chunk_id)
        normalized = " ".join(question.strip().split())
        if not normalized:
            raise ValueError("生成问题不能为空")
        metadata = dict(chunk.chunk_metadata or {})
        questions = _generated_questions(metadata)
        if not any(item["question"] == normalized for item in questions):
            questions.append({"id": str(uuid.uuid4()), "question": normalized})
        metadata["generated_questions"] = questions
        chunk.chunk_metadata = metadata
        chunk.search_text = _search_text_with_generated_questions(chunk.content, questions)
        chunk.updated_at = datetime.now(UTC)
        chunk = self.repo.save(chunk)
        self._sync_vector_payload(chunk, {"metadata": metadata})
        return chunk

    def delete_generated_question(self, chunk_id: str, question_id: str) -> Chunk:
        chunk = self.get_by_id(chunk_id)
        metadata = dict(chunk.chunk_metadata or {})
        questions = _generated_questions(metadata)
        filtered = [item for item in questions if item["id"] != question_id]
        if len(filtered) == len(questions):
            raise ValueError("生成问题不存在")
        metadata["generated_questions"] = filtered
        chunk.chunk_metadata = metadata
        chunk.search_text = _search_text_with_generated_questions(chunk.content, filtered)
        chunk.updated_at = datetime.now(UTC)
        chunk = self.repo.save(chunk)
        self._sync_vector_payload(chunk, {"metadata": metadata})
        return chunk

    def _sync_vector_payload(self, chunk: Chunk, payload: dict) -> None:
        if not payload or self.vector_store is None:
            return
        if hasattr(self.vector_store, "set_payload_for_chunk_ids"):
            self.vector_store.set_payload_for_chunk_ids(chunk_ids=[chunk.id], payload=payload)
        elif "is_enabled" in payload and hasattr(self.vector_store, "set_enabled_for_chunk_ids"):
            self.vector_store.set_enabled_for_chunk_ids(chunk_ids=[chunk.id], is_enabled=payload["is_enabled"])


def _generated_questions(metadata: dict) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in metadata.get("generated_questions") or []:
        if isinstance(raw, str):
            question_id = str(uuid.uuid4())
            question = raw.strip()
        elif isinstance(raw, dict):
            question_id = str(raw.get("id") or uuid.uuid4())
            question = str(raw.get("question") or raw.get("content") or "").strip()
        else:
            continue
        if not question or question in seen:
            continue
        seen.add(question)
        questions.append({"id": question_id, "question": question})
    return questions


def _search_text_with_generated_questions(content: str, questions: list[dict[str, str]]) -> str:
    parts = [content.strip(), *(item["question"] for item in questions if item.get("question"))]
    return "\n".join(part for part in parts if part)
