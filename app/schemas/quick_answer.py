from pydantic import BaseModel, Field


class QuickAnswerRequest(BaseModel):
    knowledge_base_id: str
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceRead(BaseModel):
    document_id: str
    knowledge_base_id: str
    chunk_id: str
    title: str | None = None
    content: str
    score: float


class QuickAnswerResponse(BaseModel):
    answer: str
    sources: list[SourceRead]
