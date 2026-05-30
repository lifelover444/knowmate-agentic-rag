from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str
    type: str
    source_type: str = "file"
    title: str
    source: str
    parse_status: str
    enable_status: str
    file_name: str | None
    file_type: str | None
    file_size: int
    storage_size: int
    embedding_model_id: str | None = None
    chunk_count: int = 0
    task_status: str | None = None
    processed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ManualTextImportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    format: str = "text"


class URLImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class BatchDocumentRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)


class BatchDocumentResponse(BaseModel):
    deleted: int = 0
    queued: int = 0
    task_ids: list[str] = Field(default_factory=list)


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
