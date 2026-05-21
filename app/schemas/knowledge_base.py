from datetime import datetime

from pydantic import BaseModel, Field


class ChunkingConfigSchema(BaseModel):
    chunk_size: int = Field(default=512, ge=50, le=10000)
    chunk_overlap: int = Field(default=80, ge=0, le=2000)


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    chunking_config: ChunkingConfigSchema | None = None


class KnowledgeBaseRead(BaseModel):
    id: str
    tenant_id: int
    name: str
    description: str | None
    chunking_config: dict
    embedding_model_id: str
    summary_model_id: str
    document_count: int = 0
    chunk_count: int = 0
    processing_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
