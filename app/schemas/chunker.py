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
    truncated_to: int | None = None


class PreviewChunkingResponse(BaseModel):
    selected_tier: str
    tier_chain: list[str]
    rejected: list[dict]
    profile: dict
    chunks: list[PreviewChunk]
    stats: PreviewChunkingStats
