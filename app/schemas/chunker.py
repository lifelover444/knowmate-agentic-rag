from pydantic import BaseModel, Field

from app.schemas.knowledge_base import ChunkingConfigSchema


class PreviewChunkingRequest(BaseModel):
    text: str = Field(max_length=64 * 1024)
    chunking_config: ChunkingConfigSchema


class PreviewChunk(BaseModel):
    seq: int
    start: int
    end: int
    size_chars: int
    size_tokens_approx: int
    context_header: str | None = None
    content: str


class PreviewChunkingStats(BaseModel):
    count: int
    avg_chars: int
    min_chars: int
    max_chars: int
    stddev_chars: int
    avg_tokens: int = 0
    min_tokens: int = 0
    max_tokens: int = 0
    stddev_tokens: int = 0
    token_limit: int | None = None
    size_distribution: dict[str, int] = Field(default_factory=dict)
    truncated_to: int | None = None


class PreviewChunkingResponse(BaseModel):
    selected_tier: str
    tier_chain: list[str]
    rejected: list[dict]
    profile: dict
    protected_blocks: dict[str, int] = Field(default_factory=dict)
    token_limit_applied: bool = False
    token_limit_reason: str = ""
    requested_chunk_size: int = 0
    effective_chunk_size: int = 0
    fallback_tier: str | None = None
    chunks: list[PreviewChunk]
    stats: PreviewChunkingStats
