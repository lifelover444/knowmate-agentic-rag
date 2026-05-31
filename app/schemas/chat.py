from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.quick_answer import SourceRead


class ChatSettings(BaseModel):
    mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    enable_rerank: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    system_prompt: str | None = None
    enable_query_rewrite: bool = False


class ChatSessionCreate(BaseModel):
    knowledge_base_id: str = Field(min_length=1, max_length=36)
    title: str | None = Field(default=None, max_length=255)
    settings: ChatSettings | None = None


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_pinned: bool | None = None
    settings: ChatSettings | None = None


class ChatSessionBatchDeleteRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=100)


class ChatSessionBatchDeleteFailure(BaseModel):
    session_id: str
    reason: str


class ChatSessionBatchDeleteResponse(BaseModel):
    requested: int
    deleted: int
    failed: int
    failures: list[ChatSessionBatchDeleteFailure] = Field(default_factory=list)


class RecommendedQuestionRead(BaseModel):
    question: str
    source_type: str
    knowledge_base_id: str
    knowledge_id: str | None = None
    chunk_id: str | None = None
    faq_id: str | None = None
    title: str | None = None


class RecommendedQuestionListResponse(BaseModel):
    items: list[RecommendedQuestionRead]


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tenant_id: int
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    original_query: str | None = None
    rewritten_query: str | None = None
    sources: list[SourceRead] = Field(default_factory=list)
    retrieval_trace: dict | None = None
    model_config_info: dict | None = Field(default=None, alias="model_config")
    status: str
    error_message: str | None = None
    created_at: datetime


class ChatSessionRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    title: str
    is_pinned: bool
    settings: dict
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionRead]


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageRead]
