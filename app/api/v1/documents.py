from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_embedder, get_settings
from app.core.config import Settings
from app.db.models import Chunk
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.task import ProcessingTaskRepository
from app.schemas.document import (
    ChunkRead,
    DocumentMoveFailure,
    DocumentMoveRequest,
    DocumentMoveResponse,
    DocumentPreviewRead,
    DocumentRead,
    ManualTextImportRequest,
    URLImportRequest,
)
from app.schemas.processing_span import ProcessingSpanTimeline
from app.services.document import DocumentService
from app.services.document_preview import DocumentPreviewService
from app.services.model_config import MODEL_CONFIG_REQUIRED_MESSAGE, ModelConfigService
from app.services.processing_spans import ProcessingSpanService
from app.services.task import TASK_DOCUMENT_REPROCESS, TASK_DOCUMENT_UPLOAD_PROCESS, ProcessingTaskService
from app.workers import tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[object, Depends(get_embedder)]
UploadDocumentFile = Annotated[UploadFile, File(...)]


@router.post("/move", response_model=DocumentMoveResponse)
def move_documents(payload: DocumentMoveRequest, db: DBSession, settings: AppSettings, request: Request):
    doc_repo = DocumentRepository(db)
    service = DocumentService(doc_repo, KnowledgeBaseRepository(db), settings, settings.upload_dir)
    moved = 0
    failures: list[DocumentMoveFailure] = []
    for document_id in payload.document_ids:
        document = doc_repo.get(document_id)
        if document is None:
            failures.append(DocumentMoveFailure(document_id=document_id, reason="文档不存在"))
            continue
        try:
            service.move_to_knowledge_base(document, payload.target_kb_id, vector_store=request.app.state.vector_store)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        moved += 1
    return DocumentMoveResponse(
        requested=len(payload.document_ids),
        moved=moved,
        failed=len(failures),
        failures=failures,
        target_kb_id=payload.target_kb_id,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: DBSession):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return to_document_read(document, db)


@router.get("/{document_id}/download")
def download_document(document_id: str, db: DBSession):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    if not document.file_path:
        raise HTTPException(status_code=404, detail="原文件不存在")
    path = Path(document.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="原文件不存在")
    filename = document.file_name or path.name
    response = FileResponse(path, filename=filename, media_type="application/octet-stream")
    response.headers["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
    return response


@router.post("/{document_id}/cancel-parse", response_model=DocumentRead)
def cancel_document_parse(document_id: str, db: DBSession, settings: AppSettings):
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        cancelled = DocumentService(
            DocumentRepository(db),
            KnowledgeBaseRepository(db),
            settings,
            settings.upload_dir,
        ).cancel_parse(document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_document_read(cancelled, db)


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


@router.get("/{document_id}/spans", response_model=ProcessingSpanTimeline)
def get_document_spans(document_id: str, db: DBSession):
    try:
        return ProcessingSpanService(db).get_timeline(document_id)
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
    try:
        document = DocumentService(
            DocumentRepository(db),
            KnowledgeBaseRepository(db),
            settings,
            settings.upload_dir,
        ).create_from_upload(kb_id, file, tag_id=tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
