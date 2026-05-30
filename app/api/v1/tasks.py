from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.task import ProcessingTaskRepository
from app.schemas.task import ProcessingTaskRead
from app.services.task import ProcessingTaskService
from app.workers import tasks as worker_tasks

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[ProcessingTaskRead])
def list_tasks(
    db: DBSession,
    settings: AppSettings,
    knowledge_base_id: str | None = None,
    document_id: str | None = None,
    status: str | None = None,
):
    return ProcessingTaskRepository(db).list(
        settings.default_tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        status=status,
    )


@router.get("/{task_id}", response_model=ProcessingTaskRead)
def get_task(task_id: str, db: DBSession, settings: AppSettings):
    task = ProcessingTaskRepository(db).get(task_id, settings.default_tenant_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/{task_id}/retry", response_model=ProcessingTaskRead, status_code=status.HTTP_202_ACCEPTED)
def retry_task(task_id: str, db: DBSession, settings: AppSettings):
    repo = ProcessingTaskRepository(db)
    task = repo.get(task_id, settings.default_tenant_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        retry = ProcessingTaskService(repo, settings).retry(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if retry.document_id:
        worker_tasks.enqueue_document_processing(retry.document_id)
    return retry
