from pydantic import BaseModel, Field


class AttachmentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = ""
    mime_type: str | None = Field(default=None, max_length=128)
    size: int | None = Field(default=None, ge=0)


class QuickAnswerRequest(BaseModel):
    knowledge_base_id: str | None = None
    knowledge_base_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    mentioned_items: list[dict] = Field(default_factory=list)
    attachments: list[AttachmentInput] = Field(default_factory=list)
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    enable_rerank: bool | None = None


class QuickAnswerStreamRequest(QuickAnswerRequest):
    session_id: str | None = None
    stream: bool | None = True
    enable_query_rewrite: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    system_prompt: str | None = None


class SourceRead(BaseModel):
    document_id: str
    knowledge_base_id: str
    knowledge_base_name: str | None = None
    chunk_id: str
    document_title: str | None = None
    title: str | None = None
    snippet: str | None = None
    source_type: str | None = None
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
    context_content: str | None = None


class QuickAnswerResponse(BaseModel):
    answer: str
    sources: list[SourceRead]
    retrieval_trace: dict | None = None
