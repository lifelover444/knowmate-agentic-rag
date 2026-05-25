from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    type: str
    title: str
    source: str
    parse_status: str
    enable_status: str
    file_name: str | None
    file_type: str | None
    file_size: int
    storage_size: int
    processed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChunkRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    knowledge_id: str
    content: str
    chunk_index: int
    is_enabled: bool
    start_at: int
    end_at: int
    pre_chunk_id: str | None
    next_chunk_id: str | None
    chunk_type: str
    parent_chunk_id: str | None = None
    context_header: str | None = None
    metadata: dict | None = Field(default=None, validation_alias="chunk_metadata")
    images: list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
