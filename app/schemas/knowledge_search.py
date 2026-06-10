from pydantic import BaseModel, Field

from app.schemas.quick_answer import SourceRead


class KnowledgeSearchRequest(BaseModel):
    knowledge_base_id: str | None = None
    knowledge_base_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    enable_rerank: bool | None = None


class KnowledgeSearchResponse(BaseModel):
    hits: list[SourceRead]
    diagnostics: dict | None = None
