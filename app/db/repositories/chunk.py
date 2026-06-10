from datetime import UTC, datetime

from sqlalchemy import bindparam, delete, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Chunk

PARADEDB_UNAVAILABLE_MESSAGE = "ParadeDB BM25 未就绪，请先安装 pg_search 扩展并执行数据库迁移。"


class ParadeDBUnavailableError(RuntimeError):
    pass


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

    def save(self, chunk: Chunk) -> Chunk:
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def soft_delete(self, chunk: Chunk) -> Chunk:
        chunk.deleted_at = datetime.now(UTC)
        chunk.is_enabled = False
        return self.save(chunk)

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
            return self._paradedb_bm25_search(
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

    def bm25_delete_by_document(self, knowledge_id: str) -> int:
        return self.soft_delete_by_document(knowledge_id)

    def bm25_upsert_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def _paradedb_bm25_search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        limit: int,
        score_threshold: float | None,
        knowledge_ids: list[str] | None,
    ) -> list[dict]:
        statement = _build_paradedb_bm25_sql(has_knowledge_ids=bool(knowledge_ids))
        params = {
            "knowledge_base_id": knowledge_base_id,
            "query": query,
            "limit": limit,
        }
        if knowledge_ids:
            params["knowledge_ids"] = list(knowledge_ids)
        try:
            rows = self.db.execute(statement, params).mappings().all()
        except SQLAlchemyError as exc:
            raise ParadeDBUnavailableError(PARADEDB_UNAVAILABLE_MESSAGE) from exc
        results = [_bm25_row(row) for row in rows]
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


def _build_paradedb_bm25_sql(*, has_knowledge_ids: bool):
    knowledge_filter = "AND knowledge_id IN :knowledge_ids" if has_knowledge_ids else ""
    statement = text(
        f"""
        SELECT
            id AS chunk_id,
            knowledge_id,
            knowledge_base_id,
            content,
            context_header,
            parent_chunk_id,
            chunk_type,
            metadata,
            metadata ->> 'title' AS title,
            pdb.score(id) AS score,
            pdb.snippet(search_text) AS snippet
        FROM chunks
        WHERE knowledge_base_id = :knowledge_base_id
          AND deleted_at IS NULL
          AND is_enabled IS TRUE
          AND chunk_type = 'child'
          {knowledge_filter}
          AND search_text ||| :query
        ORDER BY score DESC, chunk_index ASC
        LIMIT :limit
        """
    )
    if has_knowledge_ids:
        statement = statement.bindparams(bindparam("knowledge_ids", expanding=True))
    return statement


def _bm25_row(row) -> dict:
    metadata = dict(row.get("metadata") or {})
    snippet = row.get("snippet")
    if snippet:
        metadata["snippet"] = snippet
    return {
        "chunk_id": row["chunk_id"],
        "knowledge_id": row["knowledge_id"],
        "knowledge_base_id": row["knowledge_base_id"],
        "content": row["content"],
        "context_header": row.get("context_header"),
        "parent_chunk_id": row.get("parent_chunk_id"),
        "chunk_type": row.get("chunk_type"),
        "metadata": metadata,
        "title": row.get("title") or metadata.get("title"),
        "score": float(row.get("score") or 0),
        "snippet": snippet,
    }
