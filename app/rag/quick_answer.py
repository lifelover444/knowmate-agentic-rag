from dataclasses import dataclass

from app.rag.prompt import build_quick_answer_messages


@dataclass(frozen=True)
class AnswerSource:
    document_id: str
    knowledge_base_id: str
    chunk_id: str
    content: str
    score: float
    title: str | None = None
    context_header: str | None = None
    parent_chunk_id: str | None = None
    chunk_type: str | None = None
    metadata: dict | None = None
    retrieval_method: str | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    context_chunk_id: str | None = None
    context_content: str | None = None


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[AnswerSource]


class QuickAnswerEngine:
    def __init__(self, embedder, chat_model, vector_store) -> None:
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store

    def answer(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        top_k: int,
        score_threshold: float | None = None,
        final_top_k: int | None = None,
    ) -> AnswerResult:
        query_vector = self.embedder.embed(query)
        hits = _search(
            self.vector_store,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        hits = _deduplicate_hits(hits)
        if final_top_k:
            hits = hits[:final_top_k]
        if not hits:
            return AnswerResult(answer="没有在知识库中找到可引用的内容。", sources=[])

        sources = [
            AnswerSource(
                document_id=hit["knowledge_id"],
                knowledge_base_id=hit["knowledge_base_id"],
                chunk_id=hit["chunk_id"],
                content=hit["content"],
                score=float(hit["score"]),
                title=hit.get("title"),
                context_header=hit.get("context_header"),
                parent_chunk_id=hit.get("parent_chunk_id"),
                chunk_type=hit.get("chunk_type"),
                metadata=hit.get("metadata") or {},
                retrieval_method=hit.get("retrieval_method"),
                vector_score=hit.get("vector_score"),
                keyword_score=hit.get("keyword_score"),
                rrf_score=hit.get("rrf_score"),
                rerank_score=hit.get("rerank_score"),
                context_chunk_id=hit.get("context_chunk_id"),
            )
            for hit in hits
        ]
        messages = build_quick_answer_messages(
            query=query,
            contexts=[
                f"{source.context_header}\n\n{source.content}" if source.context_header else source.content
                for source in sources
            ],
        )
        return AnswerResult(answer=self.chat_model.complete(messages), sources=sources)


def _deduplicate_hits(hits: list[dict]) -> list[dict]:
    by_chunk: dict[str, dict] = {}
    for hit in hits:
        chunk_id = str(hit.get("chunk_id"))
        existing = by_chunk.get(chunk_id)
        if existing is None or float(hit.get("score") or 0) > float(existing.get("score") or 0):
            by_chunk[chunk_id] = hit
    return sorted(by_chunk.values(), key=lambda item: float(item.get("score") or 0), reverse=True)


def _search(
    vector_store,
    *,
    knowledge_base_id: str,
    query_vector: list[float],
    top_k: int,
    score_threshold: float | None,
):
    try:
        return vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )
    except TypeError:
        hits = vector_store.search(knowledge_base_id=knowledge_base_id, query_vector=query_vector, limit=top_k)
        if score_threshold is None:
            return hits
        return [hit for hit in hits if float(hit.get("score") or 0) >= score_threshold]
