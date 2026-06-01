from datetime import UTC, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Chunk


class ChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_for_document(self, knowledge_id: str, chunks: list[Chunk]) -> list[Chunk]:
        self.db.execute(delete(Chunk).where(Chunk.knowledge_id == knowledge_id))
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def list_by_document(self, knowledge_id: str) -> list[Chunk]:
        return list(
            self.db.scalars(
                select(Chunk)
                .where(Chunk.knowledge_id == knowledge_id, Chunk.deleted_at.is_(None))
                .order_by(Chunk.chunk_index.asc())
            ).all()
        )

    def get(self, chunk_id: str) -> Chunk | None:
        return self.db.scalar(select(Chunk).where(Chunk.id == chunk_id, Chunk.deleted_at.is_(None)))

    def keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        terms: list[str],
        limit: int,
        score_threshold: float | None = None,
        knowledge_ids: list[str] | None = None,
    ) -> list[dict]:
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            return self._postgres_keyword_search(
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
                score_threshold=score_threshold,
                knowledge_ids=knowledge_ids,
            )
        return self._fallback_keyword_search(
            knowledge_base_id=knowledge_base_id,
            terms=terms,
            limit=limit,
            score_threshold=score_threshold,
            knowledge_ids=knowledge_ids,
        )

    def soft_delete_by_document(self, knowledge_id: str) -> int:
        chunks = list(self.db.scalars(select(Chunk).where(Chunk.knowledge_id == knowledge_id)).all())
        now = datetime.now(UTC)
        for chunk in chunks:
            chunk.deleted_at = now
            chunk.is_enabled = False
        self.db.commit()
        return len(chunks)

    def _postgres_keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        limit: int,
        score_threshold: float | None,
        knowledge_ids: list[str] | None,
    ) -> list[dict]:
        ts_query = func.plainto_tsquery("simple", query)
        score_expr = func.ts_rank(func.to_tsvector("simple", func.coalesce(Chunk.search_text, "")), ts_query)
        statement = (
            select(Chunk, score_expr.label("score"))
            .where(
                Chunk.knowledge_base_id == knowledge_base_id,
                Chunk.deleted_at.is_(None),
                Chunk.is_enabled.is_(True),
                func.to_tsvector("simple", func.coalesce(Chunk.search_text, "")).op("@@")(ts_query),
            )
        )
        if knowledge_ids:
            statement = statement.where(Chunk.knowledge_id.in_(knowledge_ids))
        statement = statement.order_by(score_expr.desc(), Chunk.chunk_index.asc()).limit(limit)
        rows = self.db.execute(statement).all()
        results = [_keyword_row(chunk, float(score or 0)) for chunk, score in rows]
        if score_threshold is not None:
            results = [item for item in results if float(item["score"]) >= score_threshold]
        return results

    def _fallback_keyword_search(
        self,
        *,
        knowledge_base_id: str,
        terms: list[str],
        limit: int,
        score_threshold: float | None,
        knowledge_ids: list[str] | None,
    ) -> list[dict]:
        if not terms:
            return []
        conditions = [Chunk.search_text.ilike(f"%{term}%") for term in terms]
        rows = list(
            self.db.scalars(
                select(Chunk)
                .where(
                    Chunk.knowledge_base_id == knowledge_base_id,
                    Chunk.deleted_at.is_(None),
                    Chunk.is_enabled.is_(True),
                    or_(*conditions),
                )
                .order_by(Chunk.chunk_index.asc())
            ).all()
        )
        if knowledge_ids:
            allowed = set(knowledge_ids)
            rows = [chunk for chunk in rows if chunk.knowledge_id in allowed]
        scored: list[dict] = []
        for chunk in rows:
            text = (chunk.search_text or chunk.content or "").lower()
            matches = sum(1 for term in terms if term.lower() in text)
            score = matches / max(len(terms), 1)
            if score_threshold is None or score >= score_threshold:
                scored.append(_keyword_row(chunk, score))
        scored.sort(key=lambda item: float(item["score"]), reverse=True)
        return scored[:limit]


def _keyword_row(chunk: Chunk, score: float) -> dict:
    metadata = chunk.chunk_metadata or {}
    title = metadata.get("title")
    if title is None:
        title = getattr(getattr(chunk, "knowledge", None), "title", None)
    return {
        "chunk_id": chunk.id,
        "knowledge_id": chunk.knowledge_id,
        "knowledge_base_id": chunk.knowledge_base_id,
        "content": chunk.content,
        "context_header": chunk.context_header,
        "parent_chunk_id": chunk.parent_chunk_id,
        "chunk_type": chunk.chunk_type,
        "metadata": metadata,
        "title": title,
        "score": score,
    }
