from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_embedder, get_settings
from app.core.config import Settings
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.document import ChunkRead, DocumentRead
from app.services.document import DocumentService
from app.services.document_processing import DocumentProcessingService
from app.services.model_config import MODEL_CONFIG_REQUIRED_MESSAGE, ModelConfigService
from app.workers import tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[object, Depends(get_embedder)]
UploadDocumentFile = Annotated[UploadFile, File(...)]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: DBSession):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: DBSession, settings: AppSettings, request: Request):
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    DocumentService(
        repo,
        KnowledgeBaseRepository(db),
        settings,
        settings.upload_dir,
    ).soft_delete(document, vector_store=request.app.state.vector_store)
    return None


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def list_document_chunks(document_id: str, db: DBSession):
    if DocumentRepository(db).get(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return ChunkRepository(db).list_by_document(document_id)


@router.post("/{document_id}/reprocess", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(document_id: str, db: DBSession, settings: AppSettings, request: Request):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        DocumentProcessingService(
            db=db,
            upload_dir=settings.upload_dir,
            settings=settings,
            embedder=request.app.state.embedder,
            vector_store=request.app.state.vector_store,
        ).process(document_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentRepository(db).get(document_id)


def create_document_from_file(
    kb_id: str,
    file: UploadDocumentFile,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
):
    kb = KnowledgeBaseRepository(db).get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    if embedder is None:
        try:
            ModelConfigService(db, settings).get_model(kb.embedding_model_id, "Embedding")
        except (LookupError, RuntimeError):
            raise HTTPException(status_code=400, detail=MODEL_CONFIG_REQUIRED_MESSAGE) from None
    document = DocumentService(
        DocumentRepository(db),
        KnowledgeBaseRepository(db),
        settings,
        settings.upload_dir,
    ).create_from_upload(kb_id, file)
    response = DocumentRead.model_validate(document)
    tasks.enqueue_document_processing(document.id)
    return response
