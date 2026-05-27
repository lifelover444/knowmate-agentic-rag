from pydantic import BaseModel, Field


class QuickAnswerRequest(BaseModel):
    knowledge_base_id: str
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    mode: str | None = None
    enable_rerank: bool | None = None


class SourceRead(BaseModel):
    document_id: str
    knowledge_base_id: str
    chunk_id: str
    title: str | None = None
    content: str
    score: float
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


class QuickAnswerResponse(BaseModel):
    answer: str
    sources: list[SourceRead]
