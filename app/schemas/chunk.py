from pydantic import BaseModel, Field

from app.schemas.document import ChunkRead


class ChunkUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    search_text: str | None = None
    metadata: dict | None = None
    is_enabled: bool | None = None


class ChunkUpdateResponse(BaseModel):
    chunk: ChunkRead
    requires_reindex: bool = False


class GeneratedQuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class GeneratedQuestionDelete(BaseModel):
    question_id: str = Field(min_length=1)
