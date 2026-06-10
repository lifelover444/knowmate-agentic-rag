from datetime import datetime

from pydantic import BaseModel, Field


class ChunkingConfigSchema(BaseModel):
    chunk_size: int = Field(default=512, ge=50, le=10000)
    chunk_overlap: int = Field(default=80, ge=0, le=2000)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", "。"])
    strategy: str = Field(default="auto")
    token_limit: int = Field(default=0, ge=0, le=8192)
    languages: list[str] = Field(default_factory=list)
    enable_parent_child: bool = True
    parent_chunk_size: int = Field(default=4096, ge=512, le=8192)
    child_chunk_size: int = Field(default=384, ge=64, le=2048)


class ParserEngineRuleSchema(BaseModel):
    file_types: list[str]
    engine: str


class IndexingStrategySchema(BaseModel):
    enable_vector: bool = True
    enable_keyword: bool = True
    enable_parent_child: bool = True
    enable_rerank: bool = True
    enable_wiki: bool = False
    enable_knowledge_graph: bool = False


class FAQConfigSchema(BaseModel):
    index_mode: str = Field(default="question_answer")
    question_index_mode: str = Field(default="combined")


class KnowledgeBaseCapabilities(BaseModel):
    document: bool = False
    faq: bool = False
    vector: bool = False
    keyword: bool = False
    parent_child: bool = False
    rerank: bool = False
    wiki: bool = False
    graph: bool = False


class KnowledgeBasePinUpdate(BaseModel):
    pinned: bool


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    kb_type: str = Field(default="document")
    embedding_model_id: str | None = Field(default=None, max_length=128)
    summary_model_id: str | None = Field(default=None, max_length=128)
    chunking_config: ChunkingConfigSchema | None = None
    parser_engine_rules: list[ParserEngineRuleSchema] | None = None
    faq_config: FAQConfigSchema | None = None
    indexing_strategy: IndexingStrategySchema | None = None
    vector_store_id: str | None = Field(default=None, max_length=36)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    kb_type: str | None = Field(default=None)
    embedding_model_id: str | None = Field(default=None, max_length=128)
    summary_model_id: str | None = Field(default=None, max_length=128)
    chunking_config: ChunkingConfigSchema | None = None
    parser_engine_rules: list[ParserEngineRuleSchema] | None = None
    faq_config: FAQConfigSchema | None = None
    indexing_strategy: IndexingStrategySchema | None = None
    vector_store_id: str | None = Field(default=None, max_length=36)


class KnowledgeBaseRead(BaseModel):
    id: str
    tenant_id: int
    name: str
    description: str | None
    kb_type: str = "document"
    chunking_config: dict
    parser_engine_rules: list | None = None
    faq_config: dict | None = None
    indexing_strategy: dict
    vector_store_id: str | None = None
    embedding_model_id: str
    summary_model_id: str
    document_count: int = 0
    chunk_count: int = 0
    processing_count: int = 0
    capabilities: KnowledgeBaseCapabilities
    is_pinned: bool = False
    pinned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
