from pydantic import BaseModel, Field

from app.schemas.quick_answer import SourceRead


class KnowledgeSearchRequest(BaseModel):
    knowledge_base_id: str
    query: str = Field(min_length=1)
    mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    enable_rerank: bool | None = None


class KnowledgeSearchResponse(BaseModel):
    hits: list[SourceRead]
