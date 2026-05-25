from datetime import datetime

from pydantic import BaseModel, Field


class ModelConfigPayload(BaseModel):
    provider: str = Field(default="openai-compatible", min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=255)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    chat_model: str = Field(min_length=1, max_length=128)
    embedding_model: str = Field(min_length=1, max_length=128)
    embedding_dimension: int = Field(gt=0, le=4096)


class ModelConfigRead(BaseModel):
    id: str
    tenant_id: int
    provider: str
    name: str
    base_url: str
    chat_model: str
    embedding_model: str
    embedding_dimension: int
    is_active: bool
    api_key_configured: bool
    api_key_last4: str | None
    created_at: datetime
    updated_at: datetime


class ModelConfigTestResult(BaseModel):
    chat_ok: bool
    embedding_ok: bool
    detected_dimension: int | None = None
    message: str
