from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.db.repositories.chunk import ChunkRepository
from app.schemas.chunk import (
    ChunkUpdateRequest,
    ChunkUpdateResponse,
    GeneratedQuestionCreate,
    GeneratedQuestionDelete,
)
from app.schemas.document import ChunkRead
from app.services.chunk import ChunkService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]


@router.get("/by-id/{chunk_id}", response_model=ChunkRead)
def get_chunk_by_id(chunk_id: str, db: DBSession):
    try:
        return ChunkService(ChunkRepository(db)).get_by_id(chunk_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/by-id/{chunk_id}/questions", response_model=ChunkRead, status_code=status.HTTP_201_CREATED)
def add_generated_question(chunk_id: str, payload: GeneratedQuestionCreate, db: DBSession, request: Request):
    try:
        return ChunkService(
            ChunkRepository(db),
            vector_store=request.app.state.vector_store,
        ).add_generated_question(chunk_id, payload.question)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/by-id/{chunk_id}/questions", response_model=ChunkRead)
def delete_generated_question(chunk_id: str, payload: GeneratedQuestionDelete, db: DBSession, request: Request):
    try:
        return ChunkService(
            ChunkRepository(db),
            vector_store=request.app.state.vector_store,
        ).delete_generated_question(chunk_id, payload.question_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{knowledge_id}/{chunk_id}", response_model=ChunkUpdateResponse)
def update_chunk(knowledge_id: str, chunk_id: str, payload: ChunkUpdateRequest, db: DBSession, request: Request):
    try:
        chunk, requires_reindex = ChunkService(
            ChunkRepository(db),
            vector_store=request.app.state.vector_store,
        ).update(knowledge_id, chunk_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ChunkUpdateResponse(chunk=ChunkRead.model_validate(chunk), requires_reindex=requires_reindex)


@router.delete("/{knowledge_id}/{chunk_id}", response_model=ChunkRead, status_code=status.HTTP_200_OK)
def delete_chunk(knowledge_id: str, chunk_id: str, db: DBSession, request: Request):
    try:
        return ChunkService(
            ChunkRepository(db),
            vector_store=request.app.state.vector_store,
        ).disable(knowledge_id, chunk_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
