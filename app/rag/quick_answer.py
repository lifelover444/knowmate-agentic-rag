from dataclasses import dataclass


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
