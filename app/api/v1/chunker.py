import math

from fastapi import APIRouter

from app.rag.chunker import AdaptiveTextChunker, ChunkingConfig
from app.schemas.chunker import PreviewChunk, PreviewChunkingRequest, PreviewChunkingResponse, PreviewChunkingStats

router = APIRouter()


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
    avg = sum(lengths) / len(lengths) if lengths else 0
    stddev = math.sqrt(sum((length - avg) ** 2 for length in lengths) / len(lengths)) if lengths else 0
    return PreviewChunkingResponse(
        selected_tier=diagnostics.selected_tier,
        tier_chain=list(diagnostics.tier_chain),
        rejected=[{"tier": item.tier, "reason": item.reason} for item in diagnostics.rejected],
        profile=diagnostics.profile.to_dict(),
        chunks=[
            PreviewChunk(
                seq=chunk.index,
                start=chunk.start,
                end=chunk.end,
                size_chars=len(chunk.content),
                size_tokens_approx=max(1, len(chunk.embedding_content()) // 4),
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
            truncated_to=len(chunks) if len(chunks) > 100 else None,
        ),
    )
