from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.document import DocumentRead
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseRead, KnowledgeBaseUpdate
from app.services.document_processing import DocumentProcessingService
from app.services.knowledge_base import KnowledgeBaseService, normalize_chunking_config

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def to_read(kb, repo: KnowledgeBaseRepository, settings: Settings) -> KnowledgeBaseRead:
    document_count, chunk_count, processing_count = repo.counts(kb.id)
    return KnowledgeBaseRead.model_validate(
        {
            **kb.__dict__,
            "chunking_config": normalize_chunking_config(kb.chunking_config, settings),
            "document_count": document_count,
            "chunk_count": chunk_count,
            "processing_count": processing_count,
        }
    )


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    try:
        kb = KnowledgeBaseService(repo, settings).create(payload)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_read(kb, repo, settings)


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    return [to_read(kb, repo, settings) for kb in repo.list(settings.default_tenant_id)]


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: str,
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return to_read(kb, repo, settings)


@router.put("/{kb_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    try:
        updated = KnowledgeBaseService(repo, settings).update(kb, payload)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_read(updated, repo, settings)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(kb_id: str, db: DBSession, settings: AppSettings, request: Request):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    KnowledgeBaseService(repo, settings).soft_delete(kb, vector_store=request.app.state.vector_store)
    return None


@router.get("/{kb_id}/documents", response_model=list[DocumentRead])
def list_knowledge_base_documents(kb_id: str, db: DBSession, settings: AppSettings):
    repo = KnowledgeBaseRepository(db)
    if repo.get(kb_id, settings.default_tenant_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return DocumentRepository(db).list_by_knowledge_base(kb_id)


@router.post("/{kb_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_knowledge_base(kb_id: str, db: DBSession, settings: AppSettings, request: Request):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    documents = DocumentRepository(db).list_by_knowledge_base(kb_id)
    processor = DocumentProcessingService(
        db=db,
        upload_dir=settings.upload_dir,
        settings=settings,
        embedder=request.app.state.embedder,
        vector_store=request.app.state.vector_store,
    )
    for document in documents:
        processor.process(document.id)
    return {"queued": len(documents)}
