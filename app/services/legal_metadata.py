from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk
from app.rag.legal_structure import build_legal_search_text, extract_legal_metadata


@dataclass(frozen=True)
class LegalMetadataBackfillResult:
    knowledge_base_id: str
    scanned: int
    updated: int
    legal_structured: int
    vector_synced: int
    dry_run: bool


class LegalMetadataBackfillService:
    def __init__(self, db: Session, settings: Settings, vector_store=None) -> None:
        self.db = db
        self.settings = settings
        self.vector_store = vector_store

    def backfill_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        dry_run: bool = False,
        sync_vector: bool = True,
        limit: int | None = None,
    ) -> LegalMetadataBackfillResult:
        chunks = self._chunks(knowledge_base_id, limit=limit)
        updates: list[tuple[Chunk, dict, str]] = []
        legal_structured = 0
        for chunk in chunks:
            metadata = dict(chunk.chunk_metadata or {})
            title = str(metadata.get("title") or metadata.get("file_name") or "")
            legal_metadata = extract_legal_metadata(title, chunk.context_header, chunk.content)
            if legal_metadata:
                legal_structured += 1
            if not legal_metadata:
                continue
            next_metadata = {**metadata, **legal_metadata}
            next_search_text = build_legal_search_text(
                title,
                chunk.context_header,
                chunk.content,
                metadata=next_metadata,
                generated_questions=_generated_questions(next_metadata),
            )
            next_metadata["normalized_content"] = next_search_text or chunk.content
            next_metadata["search_text"] = next_search_text or chunk.content
            if next_metadata == metadata and (chunk.search_text or "") == next_search_text:
                continue
            updates.append((chunk, next_metadata, next_search_text))

        vector_synced = 0
        if not dry_run:
            now = datetime.now(UTC)
            for chunk, metadata, search_text in updates:
                chunk.chunk_metadata = metadata
                chunk.search_text = search_text
                chunk.updated_at = now
                self.db.add(chunk)
            self.db.commit()
            can_sync_vector = (
                sync_vector
                and self.vector_store is not None
                and hasattr(self.vector_store, "set_payload_for_chunk_ids")
            )
            if can_sync_vector:
                for chunk, metadata, search_text in updates:
                    if chunk.chunk_type == "parent":
                        continue
                    self.vector_store.set_payload_for_chunk_ids(
                        chunk_ids=[chunk.id],
                        payload={"metadata": metadata, "search_text": search_text},
                    )
                    vector_synced += 1

        return LegalMetadataBackfillResult(
            knowledge_base_id=knowledge_base_id,
            scanned=len(chunks),
            updated=len(updates),
            legal_structured=legal_structured,
            vector_synced=vector_synced,
            dry_run=dry_run,
        )

    def _chunks(self, knowledge_base_id: str, *, limit: int | None) -> list[Chunk]:
        statement = (
            select(Chunk)
            .where(
                Chunk.tenant_id == self.settings.default_tenant_id,
                Chunk.knowledge_base_id == knowledge_base_id,
                Chunk.deleted_at.is_(None),
                Chunk.is_enabled.is_(True),
            )
            .order_by(Chunk.knowledge_id.asc(), Chunk.chunk_index.asc())
        )
        if limit:
            statement = statement.limit(limit)
        return list(self.db.scalars(statement).all())


def _generated_questions(metadata: dict) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for item in metadata.get("generated_questions") or []:
        if isinstance(item, dict) and item.get("question"):
            questions.append({"question": str(item["question"])})
    return questions
