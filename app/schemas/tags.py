from datetime import datetime

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=32)
    sort_order: int = 0


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None


class TagRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    name: str
    color: str | None = None
    sort_order: int = 0
    knowledge_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchTagAssignmentRequest(BaseModel):
    updates: dict[str, str | None] = Field(min_length=1)


class BatchTagAssignmentResponse(BaseModel):
    updated: int = 0
