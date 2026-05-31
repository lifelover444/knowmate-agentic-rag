from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.tags import BatchTagAssignmentRequest, BatchTagAssignmentResponse, TagCreate, TagRead, TagUpdate
from app.services.tags import KnowledgeTagService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/{kb_id}/tags", response_model=list[TagRead])
def list_tags(kb_id: str, db: DBSession, settings: AppSettings, keyword: str | None = None):
    try:
        return KnowledgeTagService(db, settings).list_tags(kb_id, keyword=keyword)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{kb_id}/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(kb_id: str, payload: TagCreate, db: DBSession, settings: AppSettings):
    try:
        return KnowledgeTagService(db, settings).create_tag(kb_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{kb_id}/tags/{tag_id}", response_model=TagRead)
def update_tag(kb_id: str, tag_id: str, payload: TagUpdate, db: DBSession, settings: AppSettings):
    try:
        return KnowledgeTagService(db, settings).update_tag(kb_id, tag_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{kb_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(kb_id: str, tag_id: str, db: DBSession, settings: AppSettings):
    try:
        KnowledgeTagService(db, settings).delete_tag(kb_id, tag_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return None


@router.put("/{kb_id}/documents/tags", response_model=BatchTagAssignmentResponse)
def assign_document_tags(
    kb_id: str,
    payload: BatchTagAssignmentRequest,
    db: DBSession,
    settings: AppSettings,
    request: Request,
):
    try:
        updated = KnowledgeTagService(
            db,
            settings,
            vector_store=request.app.state.vector_store,
        ).assign_documents(kb_id, payload.updates)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BatchTagAssignmentResponse(updated=updated)


@router.put("/{kb_id}/faqs/tags", response_model=BatchTagAssignmentResponse)
def assign_faq_tags(
    kb_id: str,
    payload: BatchTagAssignmentRequest,
    db: DBSession,
    settings: AppSettings,
    request: Request,
):
    try:
        updated = KnowledgeTagService(
            db,
            settings,
            vector_store=request.app.state.vector_store,
            embedder=request.app.state.embedder,
        ).assign_faqs(kb_id, payload.updates)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BatchTagAssignmentResponse(updated=updated)
