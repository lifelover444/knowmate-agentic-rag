from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.api.v1.documents import to_document_read
from app.core.config import Settings
from app.db.repositories.document import DocumentRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.db.repositories.task import ProcessingTaskRepository
from app.schemas.document import BatchDocumentRequest, BatchDocumentResponse, DocumentRead
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseRead, KnowledgeBaseUpdate
from app.services.document import DocumentService
from app.services.knowledge_base import KnowledgeBaseService, normalize_chunking_config, normalize_indexing_strategy
from app.services.task import TASK_DOCUMENT_REPROCESS, TASK_KNOWLEDGE_BASE_REBUILD, ProcessingTaskService
from app.workers import tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def to_read(kb, repo: KnowledgeBaseRepository, settings: Settings) -> KnowledgeBaseRead:
    document_count, chunk_count, processing_count = repo.counts(kb.id)
    return KnowledgeBaseRead.model_validate(
        {
            **kb.__dict__,
            "chunking_config": normalize_chunking_config(kb.chunking_config, settings),
            "indexing_strategy": normalize_indexing_strategy(kb.indexing_strategy),
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
def list_knowledge_base_documents(
    kb_id: str,
    db: DBSession,
    settings: AppSettings,
    status: str | None = None,
    file_type: str | None = None,
    keyword: str | None = None,
):
    repo = KnowledgeBaseRepository(db)
    if repo.get(kb_id, settings.default_tenant_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    documents = DocumentRepository(db).list_by_knowledge_base(
        kb_id,
        status=status,
        file_type=file_type,
        keyword=keyword,
    )
    return [to_document_read(document, db) for document in documents]


@router.post("/{kb_id}/documents/batch-delete", response_model=BatchDocumentResponse)
def batch_delete_documents(
    kb_id: str,
    payload: BatchDocumentRequest,
    db: DBSession,
    settings: AppSettings,
    request: Request,
):
    if KnowledgeBaseRepository(db).get(kb_id, settings.default_tenant_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    doc_repo = DocumentRepository(db)
    service = DocumentService(doc_repo, KnowledgeBaseRepository(db), settings, settings.upload_dir)
    deleted = 0
    for document_id in payload.document_ids:
        document = doc_repo.get(document_id)
        if document is None or document.knowledge_base_id != kb_id:
            continue
        service.soft_delete(document, vector_store=request.app.state.vector_store)
        deleted += 1
    return BatchDocumentResponse(deleted=deleted)


@router.post(
    "/{kb_id}/documents/batch-reprocess",
    response_model=BatchDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def batch_reprocess_documents(kb_id: str, payload: BatchDocumentRequest, db: DBSession, settings: AppSettings):
    if KnowledgeBaseRepository(db).get(kb_id, settings.default_tenant_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    doc_repo = DocumentRepository(db)
    task_service = ProcessingTaskService(ProcessingTaskRepository(db), settings)
    queued = 0
    task_ids = []
    for document_id in payload.document_ids:
        document = doc_repo.get(document_id)
        if document is None or document.knowledge_base_id != kb_id:
            continue
        task = task_service.create_for_document(document, TASK_DOCUMENT_REPROCESS)
        task_ids.append(task.id)
        document.parse_status = "pending"
        doc_repo.save(document)
        tasks.enqueue_document_processing(document.id)
        queued += 1
    return BatchDocumentResponse(queued=queued, task_ids=task_ids)


@router.post("/{kb_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_knowledge_base(kb_id: str, db: DBSession, settings: AppSettings, request: Request):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    documents = DocumentRepository(db).list_by_knowledge_base(kb_id)
    task_service = ProcessingTaskService(ProcessingTaskRepository(db), settings)
    task_ids = []
    for document in documents:
        task = task_service.create_for_document(document, TASK_KNOWLEDGE_BASE_REBUILD)
        task_ids.append(task.id)
        document.parse_status = "pending"
        DocumentRepository(db).save(document)
        tasks.enqueue_document_processing(document.id)
    return {"queued": len(documents), "task_ids": task_ids}
