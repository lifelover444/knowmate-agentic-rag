import re
from dataclasses import dataclass, replace
from typing import Protocol

try:
    import jieba
except ImportError:  # pragma: no cover - dependency fallback for minimal test environments
    jieba = None


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    content: str
    score: float
    title: str | None = None
    context_header: str | None = None
    parent_chunk_id: str | None = None
    chunk_type: str | None = None
    metadata: dict | None = None
    retrieval_method: str = "vector"
    vector_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    context_chunk_id: str | None = None
    context_content: str | None = None


class Retriever(Protocol):
    def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        score_threshold: float | None = None,
    ) -> list[RetrievalHit]:
        ...


class VectorRetriever:
    def __init__(self, *, embedder, vector_store) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        score_threshold: float | None = None,
    ) -> list[RetrievalHit]:
        query_vector = self.embedder.embed(query)
        hits = _vector_search(
            self.vector_store,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [
            RetrievalHit(
                chunk_id=str(hit["chunk_id"]),
                document_id=str(hit["knowledge_id"]),
                knowledge_base_id=str(hit["knowledge_base_id"]),
                content=str(hit["content"]),
                score=float(hit.get("score") or 0),
                title=hit.get("title"),
                context_header=hit.get("context_header"),
                parent_chunk_id=hit.get("parent_chunk_id"),
                chunk_type=hit.get("chunk_type"),
                metadata=hit.get("metadata") or {},
                retrieval_method="vector",
                vector_score=float(hit.get("score") or 0),
            )
            for hit in hits
        ]


class KeywordRetriever:
    def __init__(self, chunk_repo) -> None:
        self.chunk_repo = chunk_repo

    def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        score_threshold: float | None = None,
    ) -> list[RetrievalHit]:
        terms = tokenize_query(query)
        rows = self.chunk_repo.keyword_search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            terms=terms,
            limit=limit,
            score_threshold=score_threshold,
        )
        return [
            RetrievalHit(
                chunk_id=row["chunk_id"],
                document_id=row["knowledge_id"],
                knowledge_base_id=row["knowledge_base_id"],
                content=row["content"],
                score=float(row["score"]),
                title=row.get("title"),
                context_header=row.get("context_header"),
                parent_chunk_id=row.get("parent_chunk_id"),
                chunk_type=row.get("chunk_type"),
                metadata=row.get("metadata") or {},
                retrieval_method="keyword",
                keyword_score=float(row["score"]),
            )
            for row in rows
        ]


class HybridRetriever:
    def __init__(
        self,
        *,
        vector_retriever: Retriever,
        keyword_retriever: Retriever,
        rrf_k: int,
        vector_weight: float,
        keyword_weight: float,
    ) -> None:
        self.vector_retriever = vector_retriever
        self.keyword_retriever = keyword_retriever
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        score_threshold: float | None = None,
    ) -> list[RetrievalHit]:
        vector_hits = self.vector_retriever.search(query, knowledge_base_id=knowledge_base_id, limit=limit)
        keyword_hits = self.keyword_retriever.search(query, knowledge_base_id=knowledge_base_id, limit=limit)
        merged: dict[str, RetrievalHit] = {}
        rrf_scores: dict[str, float] = {}

        for rank, hit in enumerate(vector_hits, start=1):
            merged[hit.chunk_id] = hit
            rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + self.vector_weight / (self.rrf_k + rank)
        for rank, hit in enumerate(keyword_hits, start=1):
            existing = merged.get(hit.chunk_id)
            if existing is None:
                merged[hit.chunk_id] = hit
            else:
                merged[hit.chunk_id] = replace(existing, keyword_score=hit.keyword_score or hit.score)
            rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + self.keyword_weight / (self.rrf_k + rank)

        results = [
            replace(
                hit,
                retrieval_method="hybrid" if hit.chunk_id in rrf_scores else hit.retrieval_method,
                score=rrf_scores.get(hit.chunk_id, hit.score),
                rrf_score=rrf_scores.get(hit.chunk_id),
                vector_score=hit.vector_score,
                keyword_score=hit.keyword_score,
            )
            for hit in merged.values()
        ]
        results.sort(key=lambda item: float(item.rrf_score or item.score or 0), reverse=True)
        if score_threshold is not None:
            results = [item for item in results if float(item.score or 0) >= score_threshold]
        return results[:limit]


class RerankPipeline:
    def __init__(self, reranker, *, threshold: float, top_k: int) -> None:
        self.reranker = reranker
        self.threshold = threshold
        self.top_k = top_k

    def apply(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        documents: list[str] = []
        hit_indexes: list[int] = []
        for index, hit in enumerate(hits):
            passage = clean_rerank_passage(hit.context_content or hit.content)
            if not passage:
                continue
            documents.append(passage)
            hit_indexes.append(index)
        if not documents:
            return []
        reranked = self.reranker.rerank(query=query, documents=documents, top_n=min(self.top_k, len(documents)))
        results: list[RetrievalHit] = []
        for passage_index, score in reranked:
            if score < self.threshold:
                continue
            original_index = hit_indexes[passage_index]
            results.append(replace(hits[original_index], score=score, rerank_score=score))
        return results[: self.top_k]


class ParentChildExpander:
    def __init__(self, chunk_repo) -> None:
        self.chunk_repo = chunk_repo

    def expand(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        expanded: list[RetrievalHit] = []
        for hit in hits:
            if hit.chunk_type != "child" or not hit.parent_chunk_id:
                expanded.append(hit)
                continue
            parent = self.chunk_repo.get(hit.parent_chunk_id)
            if parent is None:
                expanded.append(hit)
                continue
            expanded.append(
                replace(
                    hit,
                    context_chunk_id=parent.id,
                    context_content=parent.content,
                    context_header=parent.context_header or hit.context_header,
                )
            )
        return expanded


def clean_rerank_passage(content: str, *, max_chars: int = 4000) -> str:
    without_code = re.sub(r"```.*?```", " ", content or "", flags=re.DOTALL)
    lines = []
    for line in without_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            continue
        lines.append(stripped)
    cleaned = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return cleaned[:max_chars]


def tokenize_query(query: str) -> list[str]:
    if jieba is not None:
        terms = [item.strip().lower() for item in jieba.cut(query) if item.strip()]
    else:
        terms = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
    expanded: list[str] = []
    for term in terms:
        expanded.append(term)
        if re.search(r"[\u4e00-\u9fff]", term) and len(term) > 1:
            expanded.extend(term)
    return [term for term in expanded if len(term) > 1 or re.match(r"[\u4e00-\u9fff]", term)]


def _vector_search(vector_store, *, knowledge_base_id: str, query_vector: list[float], limit: int, score_threshold):
    try:
        return vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )
    except TypeError:
        hits = vector_store.search(knowledge_base_id=knowledge_base_id, query_vector=query_vector, limit=limit)
        if score_threshold is None:
            return hits
        return [hit for hit in hits if float(hit.get("score") or 0) >= score_threshold]
