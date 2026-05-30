from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.faq import FAQEntryRepository
from app.schemas.faq import FAQEntryCreate, FAQEntryRead, FAQEntryUpdate
from app.services.faq import FAQEntryService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[FAQEntryRead])
def list_faq_entries(kb_id: str, db: DBSession):
    return FAQEntryRepository(db).list_by_knowledge_base(kb_id)


@router.post("", response_model=FAQEntryRead, status_code=status.HTTP_201_CREATED)
def create_faq_entry(kb_id: str, payload: FAQEntryCreate, db: DBSession, settings: AppSettings, request: Request):
    try:
        return FAQEntryService(
            db,
            settings,
            vector_store=request.app.state.vector_store,
            embedder=request.app.state.embedder,
        ).create(kb_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{faq_id}", response_model=FAQEntryRead)
def update_faq_entry(
    kb_id: str,
    faq_id: str,
    payload: FAQEntryUpdate,
    db: DBSession,
    settings: AppSettings,
    request: Request,
):
    entry = FAQEntryRepository(db).get(faq_id, settings.default_tenant_id)
    if entry is None or entry.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="FAQ 条目不存在")
    try:
        return FAQEntryService(
            db,
            settings,
            vector_store=request.app.state.vector_store,
            embedder=request.app.state.embedder,
        ).update(entry, payload)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq_entry(kb_id: str, faq_id: str, db: DBSession, settings: AppSettings, request: Request):
    entry = FAQEntryRepository(db).get(faq_id, settings.default_tenant_id)
    if entry is None or entry.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="FAQ 条目不存在")
    FAQEntryService(
        db,
        settings,
        vector_store=request.app.state.vector_store,
        embedder=request.app.state.embedder,
    ).delete(entry)
    return None


@router.post("/{faq_id}/rebuild-index", response_model=FAQEntryRead, status_code=status.HTTP_202_ACCEPTED)
def rebuild_faq_entry_index(kb_id: str, faq_id: str, db: DBSession, settings: AppSettings, request: Request):
    entry = FAQEntryRepository(db).get(faq_id, settings.default_tenant_id)
    if entry is None or entry.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="FAQ 条目不存在")
    try:
        FAQEntryService(
            db,
            settings,
            vector_store=request.app.state.vector_store,
            embedder=request.app.state.embedder,
        ).rebuild_index(entry)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FAQEntryRepository(db).get(faq_id, settings.default_tenant_id)
