from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_chat_model, get_db, get_embedder, get_settings, get_vector_store
from app.core.config import Settings
from app.schemas.quick_answer import QuickAnswerRequest, QuickAnswerResponse, SourceRead
from app.services.quick_answer import QuickAnswerService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[object, Depends(get_embedder)]
ChatModelDep = Annotated[object, Depends(get_chat_model)]
VectorStoreDep = Annotated[object, Depends(get_vector_store)]


@router.post("", response_model=QuickAnswerResponse)
def quick_answer(
    payload: QuickAnswerRequest,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
    chat_model: ChatModelDep,
    vector_store: VectorStoreDep,
):
    try:
        result = QuickAnswerService(db, settings, embedder, chat_model, vector_store).answer(
            knowledge_base_id=payload.knowledge_base_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuickAnswerResponse(
        answer=result.answer,
        sources=[
            SourceRead(
                document_id=source.document_id,
                knowledge_base_id=source.knowledge_base_id,
                chunk_id=source.chunk_id,
                title=source.title,
                content=source.content,
                score=source.score,
                context_header=source.context_header,
                parent_chunk_id=source.parent_chunk_id,
                chunk_type=source.chunk_type,
                metadata=source.metadata,
            )
            for source in result.sources
        ],
    )
