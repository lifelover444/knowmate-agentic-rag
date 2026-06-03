import math

from fastapi import APIRouter

from app.rag.chunker import (
    AdaptiveTextChunker,
    ChunkingConfig,
    approx_token_count,
    config_language,
    protected_block_stats,
)
from app.schemas.chunker import PreviewChunk, PreviewChunkingRequest, PreviewChunkingResponse, PreviewChunkingStats

router = APIRouter()


def chunk_size_distribution(lengths: list[int], target_size: int) -> dict[str, int]:
    if not lengths:
        return {"small": 0, "target": 0, "large": 0}
    lower = max(1, int(target_size * 0.5))
    upper = max(lower, int(target_size * 1.2))
    return {
        "small": sum(1 for length in lengths if length < lower),
        "target": sum(1 for length in lengths if lower <= length <= upper),
        "large": sum(1 for length in lengths if length > upper),
    }


@router.post("/preview", response_model=PreviewChunkingResponse)
def preview_chunking(payload: PreviewChunkingRequest):
    data = payload.chunking_config.model_dump()
    config = ChunkingConfig(
        chunk_size=data["chunk_size"],
        chunk_overlap=data["chunk_overlap"],
        separators=data["separators"],
        strategy=data["strategy"],
        token_limit=data["token_limit"],
        languages=data["languages"],
    )
    chunks, diagnostics = AdaptiveTextChunker(config).split_with_diagnostics(payload.text)
    lengths = [len(chunk.content) for chunk in chunks]
    token_language = (
        config_language(config.languages)
        if config.languages
        else (diagnostics.profile.detected_langs[0] if diagnostics.profile.detected_langs else "mixed")
    )
    token_lengths = [approx_token_count(chunk.embedding_content(), token_language) for chunk in chunks]
    avg = sum(lengths) / len(lengths) if lengths else 0
    stddev = math.sqrt(sum((length - avg) ** 2 for length in lengths) / len(lengths)) if lengths else 0
    token_avg = sum(token_lengths) / len(token_lengths) if token_lengths else 0
    token_stddev = 0
    if token_lengths:
        token_stddev = math.sqrt(sum((length - token_avg) ** 2 for length in token_lengths) / len(token_lengths))
    return PreviewChunkingResponse(
        selected_tier=diagnostics.selected_tier,
        tier_chain=list(diagnostics.tier_chain),
        rejected=[{"tier": item.tier, "reason": item.reason} for item in diagnostics.rejected],
        profile=diagnostics.profile.to_dict(),
        protected_blocks=protected_block_stats(payload.text),
        token_limit_applied=diagnostics.token_limit_applied,
        token_limit_reason=diagnostics.token_limit_reason,
        requested_chunk_size=diagnostics.requested_chunk_size,
        effective_chunk_size=diagnostics.effective_chunk_size,
        fallback_tier=diagnostics.fallback_tier,
        chunks=[
            PreviewChunk(
                seq=chunk.index,
                start=chunk.start,
                end=chunk.end,
                size_chars=len(chunk.content),
                size_tokens_approx=approx_token_count(chunk.embedding_content(), token_language),
                context_header=chunk.context_header or None,
                content=chunk.content,
            )
            for chunk in chunks[:100]
        ],
        stats=PreviewChunkingStats(
            count=len(chunks),
            avg_chars=round(avg),
            min_chars=min(lengths) if lengths else 0,
            max_chars=max(lengths) if lengths else 0,
            stddev_chars=round(stddev),
            avg_tokens=round(token_avg),
            min_tokens=min(token_lengths) if token_lengths else 0,
            max_tokens=max(token_lengths) if token_lengths else 0,
            stddev_tokens=round(token_stddev),
            token_limit=config.token_limit or None,
            size_distribution=chunk_size_distribution(lengths, config.chunk_size),
            truncated_to=len(chunks) if len(chunks) > 100 else None,
        ),
    )
