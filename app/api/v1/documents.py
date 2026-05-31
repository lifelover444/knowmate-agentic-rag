from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_embedder, get_settings
from app.core.config import Settings
from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.task import ProcessingTaskRepository
from app.schemas.document import ChunkRead, DocumentPreviewRead, DocumentRead, ManualTextImportRequest, URLImportRequest
from app.services.document import DocumentService
from app.services.document_preview import DocumentPreviewService
from app.services.model_config import MODEL_CONFIG_REQUIRED_MESSAGE, ModelConfigService
from app.services.task import TASK_DOCUMENT_REPROCESS, TASK_DOCUMENT_UPLOAD_PROCESS, ProcessingTaskService
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
    return to_document_read(document, db)


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


@router.get("/{document_id}/preview", response_model=DocumentPreviewRead)
def get_document_preview(document_id: str, db: DBSession):
    try:
        return DocumentPreviewService(db).build_preview(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/reprocess", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(document_id: str, db: DBSession, settings: AppSettings):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    ProcessingTaskService(ProcessingTaskRepository(db), settings).create_for_document(
        document,
        TASK_DOCUMENT_REPROCESS,
    )
    document.parse_status = "pending"
    DocumentRepository(db).save(document)
    tasks.enqueue_document_processing(document_id)
    return to_document_read(DocumentRepository(db).get(document_id), db)


def create_document_from_file(
    kb_id: str,
    file: UploadDocumentFile,
    db: DBSession,
    settings: AppSettings,
    embedder: EmbedderDep,
    tag_id: str | None = None,
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
    ).create_from_upload(kb_id, file, tag_id=tag_id)
    ProcessingTaskService(ProcessingTaskRepository(db), settings).create_for_document(
        document,
        TASK_DOCUMENT_UPLOAD_PROCESS,
    )
    response = to_document_read(document, db)
    tasks.enqueue_document_processing(document.id)
    return response


def create_document_from_text(
    kb_id: str,
    payload: ManualTextImportRequest,
    db: DBSession,
    settings: AppSettings,
):
    file_type = "md" if payload.format in {"markdown", "md"} else "txt"
    try:
        document = DocumentService(
            DocumentRepository(db),
            KnowledgeBaseRepository(db),
            settings,
            settings.upload_dir,
        ).create_from_text(
            kb_id,
            title=payload.title,
            content=payload.content,
            source_type="manual_text",
            file_type=file_type,
            source="manual_text",
            metadata={"format": payload.format},
            tag_id=payload.tag_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ProcessingTaskService(ProcessingTaskRepository(db), settings).create_for_document(
        document,
        TASK_DOCUMENT_UPLOAD_PROCESS,
    )
    tasks.enqueue_document_processing(document.id)
    return to_document_read(document, db)


def create_document_from_url(
    kb_id: str,
    payload: URLImportRequest,
    db: DBSession,
    settings: AppSettings,
):
    try:
        document = DocumentService(
            DocumentRepository(db),
            KnowledgeBaseRepository(db),
            settings,
            settings.upload_dir,
        ).create_from_url(kb_id, payload.url, tag_id=payload.tag_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ProcessingTaskService(ProcessingTaskRepository(db), settings).create_for_document(
        document,
        TASK_DOCUMENT_UPLOAD_PROCESS,
    )
    tasks.enqueue_document_processing(document.id)
    return to_document_read(document, db)


def to_document_read(document, db: Session) -> dict:
    if document is None:
        return {}
    chunk_count = db.query(Chunk).filter_by(
        knowledge_id=document.id,
        deleted_at=None,
    ).count()
    latest_task = next(iter(ProcessingTaskRepository(db).list(document.tenant_id, document_id=document.id)), None)
    return {
        **document.__dict__,
        "chunk_count": chunk_count,
        "task_status": latest_task.status if latest_task else None,
    }
