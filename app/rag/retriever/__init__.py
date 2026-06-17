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
    knowledge_base_name: str | None = None
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
        knowledge_ids: list[str] | None = None,
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
        knowledge_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        query_vector = self.embedder.embed(query)
        hits = _vector_search(
            self.vector_store,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            knowledge_ids=knowledge_ids,
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
        knowledge_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        terms = tokenize_query(query)
        rows = self.chunk_repo.keyword_search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            terms=terms,
            limit=limit,
            score_threshold=score_threshold,
            knowledge_ids=knowledge_ids,
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
        knowledge_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        vector_hits = _search_with_optional_knowledge_ids(
            self.vector_retriever,
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            knowledge_ids=knowledge_ids,
        )
        keyword_hits = _search_with_optional_knowledge_ids(
            self.keyword_retriever,
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            knowledge_ids=knowledge_ids,
        )
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
        self.diagnostics: dict = {}

    def apply(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        self.diagnostics = {
            "original_threshold": self.threshold,
            "degraded_threshold": None,
            "top1_fallback": False,
            "mmr_input_count": 0,
            "mmr_output_count": 0,
        }
        documents: list[str] = []
        hit_indexes: list[int] = []
        for index, hit in enumerate(hits):
            passage = build_rerank_passage(hit)
            if not passage:
                continue
            documents.append(passage)
            hit_indexes.append(index)
        if not documents:
            return []
        top_n = min(max(self.top_k * 2, self.top_k), len(documents))
        reranked = self.reranker.rerank(query=query, documents=documents, top_n=top_n)
        filtered = self._filter_reranked(reranked, self.threshold)
        if not filtered and self.threshold > 0.3:
            degraded_threshold = round(max(self.threshold * 0.7, 0.3), 2)
            self.diagnostics["degraded_threshold"] = degraded_threshold
            reranked = self.reranker.rerank(query=query, documents=documents, top_n=top_n)
            filtered = self._filter_reranked(reranked, degraded_threshold)
        if not filtered and reranked and reranked[0][1] >= 0.15:
            filtered = reranked[:1]
            self.diagnostics["top1_fallback"] = True
        results: list[RetrievalHit] = []
        score_details: list[dict] = []
        for passage_index, score in filtered:
            original_index = hit_indexes[passage_index]
            hit = hits[original_index]
            base_score = float(hit.score or 0)
            lexical_score = 0.0 if _is_faq_candidate(hit) else _lexical_relevance_score(query, documents[passage_index])
            composite_score = _composite_score(
                hit,
                model_score=score,
                base_score=base_score,
                lexical_score=lexical_score,
            )
            metadata = dict(hit.metadata or {})
            metadata.update(
                {
                    "base_score": base_score,
                    "rerank_score": score,
                    "lexical_score": lexical_score,
                    "composite_score": composite_score,
                }
            )
            results.append(replace(hit, score=composite_score, rerank_score=score, metadata=metadata))
            score_details.append(
                {
                    "chunk_id": hit.chunk_id,
                    "base_score": base_score,
                    "rerank_score": score,
                    "lexical_score": lexical_score,
                    "composite_score": composite_score,
                }
            )
        results.sort(key=lambda item: float(item.score or 0), reverse=True)
        score_details.sort(key=lambda item: float(item["composite_score"]), reverse=True)
        self.diagnostics["score_details"] = score_details[:10]
        self.diagnostics["mmr_input_count"] = len(results)
        results = _apply_mmr(results, self.top_k)
        self.diagnostics["mmr_output_count"] = len(results)
        return results

    def _filter_reranked(self, reranked: list[tuple[int, float]], threshold: float) -> list[tuple[int, float]]:
        return [(index, score) for index, score in reranked if score >= threshold]


class ParentChildExpander:
    short_context_min_chars = 350
    short_context_max_chars = 850

    def __init__(self, chunk_repo) -> None:
        self.chunk_repo = chunk_repo

    def expand(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        expanded: list[RetrievalHit] = []
        for hit in hits:
            if hit.chunk_type != "child" or not hit.parent_chunk_id:
                expanded.append(self._expand_short_text_with_neighbors(hit))
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

    def _expand_short_text_with_neighbors(self, hit: RetrievalHit) -> RetrievalHit:
        if hit.chunk_type != "text" or len(hit.content or "") >= self.short_context_min_chars:
            return hit
        base = self.chunk_repo.get(hit.chunk_id)
        if base is None or not _chunk_enabled(base) or base.chunk_type != "text":
            return hit
        prev_chunk = self._neighbor_chunk(getattr(base, "pre_chunk_id", None), base.knowledge_id)
        next_chunk = self._neighbor_chunk(getattr(base, "next_chunk_id", None), base.knowledge_id)
        parts = [chunk.content for chunk in (prev_chunk, base, next_chunk) if chunk is not None and chunk.content]
        merged = _merge_neighbor_parts(parts, max_chars=self.short_context_max_chars)
        if not merged or merged == hit.content:
            return hit
        metadata = dict(hit.metadata or {})
        metadata["context_merge"] = {
            "strategy": "neighbor",
            "chunk_ids": [
                chunk.id for chunk in (prev_chunk, base, next_chunk) if chunk is not None and getattr(chunk, "id", None)
            ],
        }
        return replace(
            hit,
            context_chunk_id=base.id,
            context_content=merged,
            context_header=base.context_header or hit.context_header,
            metadata=metadata,
        )

    def _neighbor_chunk(self, chunk_id: str | None, knowledge_id: str):
        if not chunk_id:
            return None
        chunk = self.chunk_repo.get(chunk_id)
        if chunk is None or not _chunk_enabled(chunk):
            return None
        if chunk.knowledge_id != knowledge_id or chunk.chunk_type != "text":
            return None
        return chunk


def _chunk_enabled(chunk) -> bool:
    return getattr(chunk, "is_enabled", True) is not False and getattr(chunk, "deleted_at", None) is None


def _merge_neighbor_parts(parts: list[str], *, max_chars: int) -> str:
    merged_parts: list[str] = []
    for part in parts:
        text = (part or "").strip()
        if text and text not in merged_parts:
            merged_parts.append(text)
    merged = "\n".join(merged_parts).strip()
    return merged[:max_chars].rstrip()


def clean_rerank_passage(content: str, *, max_chars: int = 4000) -> str:
    without_code = re.sub(r"```.*?```", " ", content or "", flags=re.DOTALL)
    lines = []
    for line in without_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.fullmatch(r"\|[\s:|-]+\|", stripped):
                continue
            stripped = " ".join(cell.strip() for cell in stripped.strip("|").split("|") if cell.strip())
        lines.append(stripped)
    cleaned = " ".join(lines)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://[^\s)\]>]+", " ", cleaned)
    cleaned = re.sub(r"(?m)^#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


def build_rerank_passage(hit: RetrievalHit, *, max_chars: int = 4000) -> str:
    parts: list[str] = []
    if hit.context_header:
        parts.append(hit.context_header)
    body = hit.context_content or hit.content
    if body:
        parts.append(body)
    metadata = hit.metadata or {}
    generated_questions = _metadata_generated_questions(metadata)
    if generated_questions:
        parts.append(" ".join(generated_questions))
    image_text = _metadata_image_text(metadata)
    if image_text:
        parts.append(image_text)
    return clean_rerank_passage("\n".join(parts), max_chars=max_chars)


def _metadata_generated_questions(metadata: dict) -> list[str]:
    questions: list[str] = []
    for item in metadata.get("generated_questions") or []:
        if isinstance(item, dict):
            question = str(item.get("question") or "").strip()
        else:
            question = str(item or "").strip()
        if question:
            questions.append(question)
    return questions


def _metadata_image_text(metadata: dict) -> str:
    values: list[str] = []
    for key in ("image_ocr_text", "image_caption", "ocr_text", "caption"):
        value = str(metadata.get(key) or "").strip()
        if value:
            values.append(value)
    return "\n".join(values)


def _composite_score(hit: RetrievalHit, *, model_score: float, base_score: float, lexical_score: float) -> float:
    source_weight = 0.95 if str((hit.metadata or {}).get("source_type") or "").lower() == "web_search" else 1.0
    composite = (
        0.3 * float(model_score or 0)
        + 0.1 * float(base_score or 0)
        + 0.5 * float(lexical_score or 0)
        + 0.1 * source_weight
    )
    if _is_faq_candidate(hit):
        composite = max(composite, float(base_score or 0))
    return max(0.0, min(1.0, composite))


def _is_faq_candidate(hit: RetrievalHit) -> bool:
    metadata = hit.metadata or {}
    return hit.chunk_type == "faq" or str(metadata.get("source_type") or "").lower() == "faq"


def _lexical_relevance_score(query: str, passage: str) -> float:
    terms = _lexical_query_terms(query)
    if not terms:
        return 0.0
    normalized_passage = _normalize_lexical_text(passage)
    matched_weight = 0.0
    total_weight = 0.0
    for term in terms:
        weight = _lexical_term_weight(term)
        total_weight += weight
        if _normalize_lexical_text(term) in normalized_passage:
            matched_weight += weight
    return matched_weight / total_weight if total_weight else 0.0


def _lexical_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in tokenize_query(query):
        normalized = _normalize_lexical_text(term)
        if len(normalized) < 2 or normalized in _LEXICAL_STOP_TERMS or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(term)
        for synonym in _LEXICAL_SYNONYMS.get(normalized, ()):
            synonym_normalized = _normalize_lexical_text(synonym)
            if synonym_normalized not in seen:
                seen.add(synonym_normalized)
                terms.append(synonym)
    return terms


def _normalize_lexical_text(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").lower())


def _lexical_term_weight(term: str) -> float:
    normalized = _normalize_lexical_text(term)
    if any("\u4e00" <= char <= "\u9fff" for char in normalized):
        return 2.0 if len(normalized) >= 4 else 1.2
    return 1.5 if len(normalized) >= 6 else 1.0


_LEXICAL_STOP_TERMS = {
    "是否",
    "需要",
    "承担",
    "责任",
    "损失",
    "如果",
    "什么",
    "由谁",
    "可以",
    "不能",
    "问题",
}

_LEXICAL_SYNONYMS = {
    "交强险": ("强制保险", "机动车强制保险"),
    "商业三者险": ("商业保险", "商业第三者责任保险"),
    "三者险": ("商业保险", "商业第三者责任保险"),
}


def _apply_mmr(hits: list[RetrievalHit], top_k: int, *, lambda_mult: float = 0.7) -> list[RetrievalHit]:
    if top_k <= 0 or not hits:
        return []
    selected: list[RetrievalHit] = []
    selected_token_sets: list[set[str]] = []
    candidate_token_sets = [_simple_token_set(build_rerank_passage(hit)) for hit in hits]
    selected_indexes: set[int] = set()
    while len(selected) < top_k and len(selected_indexes) < len(hits):
        best_index = -1
        best_score = float("-inf")
        for index, hit in enumerate(hits):
            if index in selected_indexes:
                continue
            redundancy = max(
                (_jaccard(candidate_token_sets[index], selected_tokens) for selected_tokens in selected_token_sets),
                default=0.0,
            )
            mmr_score = lambda_mult * float(hit.score or 0) - (1 - lambda_mult) * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_index = index
        if best_index < 0:
            break
        selected.append(hits[best_index])
        selected_token_sets.append(candidate_token_sets[best_index])
        selected_indexes.add(best_index)
    return selected


def _simple_token_set(content: str) -> set[str]:
    return set(tokenize_query(content or ""))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _search_with_optional_knowledge_ids(
    retriever,
    query: str,
    *,
    knowledge_base_id: str,
    limit: int,
    knowledge_ids: list[str] | None,
):
    try:
        return retriever.search(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            knowledge_ids=knowledge_ids,
        )
    except TypeError:
        return retriever.search(query, knowledge_base_id=knowledge_base_id, limit=limit)


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


def _vector_search(
    vector_store,
    *,
    knowledge_base_id: str,
    query_vector: list[float],
    limit: int,
    score_threshold,
    knowledge_ids: list[str] | None,
):
    try:
        return vector_store.search(
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            knowledge_ids=knowledge_ids,
        )
    except TypeError:
        hits = vector_store.search(knowledge_base_id=knowledge_base_id, query_vector=query_vector, limit=limit)
        if knowledge_ids:
            allowed = set(knowledge_ids)
            hits = [hit for hit in hits if str(hit.get("knowledge_id")) in allowed]
        if score_threshold is not None:
            hits = [hit for hit in hits if float(hit.get("score") or 0) >= score_threshold]
        return hits
