from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_embedder, get_settings, get_vector_store
from app.core.config import Settings
from app.schemas.knowledge_search import KnowledgeSearchRequest, KnowledgeSearchResponse
from app.schemas.quick_answer import SourceRead
from app.services.knowledge_search import KnowledgeSearchService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[object, Depends(get_embedder)]
VectorStoreDep = Annotated[object, Depends(get_vector_store)]


@router.post("", response_model=KnowledgeSearchResponse)
def knowledge_search(
    payload: KnowledgeSearchRequest,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
    vector_store: VectorStoreDep,
):
    try:
        hits = KnowledgeSearchService(db, settings, embedder, vector_store).search(
            knowledge_base_id=payload.knowledge_base_id,
            query=payload.query,
            mode=payload.mode,
            top_k=payload.top_k,
            enable_rerank=payload.enable_rerank,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeSearchResponse(hits=[_to_source(hit) for hit in hits])


def _to_source(hit) -> SourceRead:
    return SourceRead(
        document_id=hit.document_id,
        knowledge_base_id=hit.knowledge_base_id,
        chunk_id=hit.chunk_id,
        title=hit.title,
        content=hit.content,
        score=hit.score,
        context_header=hit.context_header,
        parent_chunk_id=hit.parent_chunk_id,
        chunk_type=hit.chunk_type,
        metadata=hit.metadata,
        retrieval_method=hit.retrieval_method,
        vector_score=hit.vector_score,
        keyword_score=hit.keyword_score,
        rrf_score=hit.rrf_score,
        rerank_score=hit.rerank_score,
        context_chunk_id=hit.context_chunk_id,
        context_content=hit.context_content,
    )
