from datetime import datetime

from pydantic import BaseModel, Field


class ChunkingConfigSchema(BaseModel):
    chunk_size: int = Field(default=512, ge=50, le=10000)
    chunk_overlap: int = Field(default=80, ge=0, le=2000)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", "。"])
    strategy: str = Field(default="auto")
    token_limit: int = Field(default=0, ge=0, le=8192)
    languages: list[str] = Field(default_factory=list)
    enable_parent_child: bool = False
    parent_chunk_size: int = Field(default=4096, ge=512, le=8192)
    child_chunk_size: int = Field(default=384, ge=64, le=2048)


class ParserEngineRuleSchema(BaseModel):
    file_types: list[str]
    engine: str


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    chunking_config: ChunkingConfigSchema | None = None
    parser_engine_rules: list[ParserEngineRuleSchema] | None = None


class KnowledgeBaseRead(BaseModel):
    id: str
    tenant_id: int
    name: str
    description: str | None
    chunking_config: dict
    parser_engine_rules: list | None = None
    embedding_model_id: str
    summary_model_id: str
    document_count: int = 0
    chunk_count: int = 0
    processing_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
