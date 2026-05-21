from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.document import ChunkRead, DocumentRead
from app.services.document import DocumentService
from app.workers import tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
UploadDocumentFile = Annotated[UploadFile, File(...)]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: DBSession):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def list_document_chunks(document_id: str, db: DBSession):
    if DocumentRepository(db).get(document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return ChunkRepository(db).list_by_document(document_id)


def create_document_from_file(
    kb_id: str,
    file: UploadDocumentFile,
    db: DBSession,
    settings: AppSettings,
):
    document = DocumentService(
        DocumentRepository(db),
        KnowledgeBaseRepository(db),
        settings,
        settings.upload_dir,
    ).create_from_upload(kb_id, file)
    response = DocumentRead.model_validate(document)
    tasks.enqueue_document_processing(document.id)
    return response
