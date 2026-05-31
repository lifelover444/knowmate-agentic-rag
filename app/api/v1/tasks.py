from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.models import ProcessingTask
from app.db.repositories.task import ProcessingTaskRepository
from app.schemas.task import ProcessingTaskBatchSummary, ProcessingTaskFailure, ProcessingTaskRead
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
    repo = ProcessingTaskRepository(db)
    task_rows = repo.list(
        settings.default_tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        status=status,
    )
    return [_to_task_read(task, _batch_summary(repo, task, settings.default_tenant_id)) for task in task_rows]


@router.get("/{task_id}", response_model=ProcessingTaskRead)
def get_task(task_id: str, db: DBSession, settings: AppSettings):
    task = ProcessingTaskRepository(db).get(task_id, settings.default_tenant_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    repo = ProcessingTaskRepository(db)
    return _to_task_read(task, _batch_summary(repo, task, settings.default_tenant_id))


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
    return _to_task_read(retry, _batch_summary(repo, retry, settings.default_tenant_id))


def _to_task_read(task: ProcessingTask, batch_summary: ProcessingTaskBatchSummary | None = None) -> ProcessingTaskRead:
    return ProcessingTaskRead.model_validate({**task.__dict__, "batch_summary": batch_summary})


def _batch_summary(
    repo: ProcessingTaskRepository,
    task: ProcessingTask,
    tenant_id: int,
) -> ProcessingTaskBatchSummary | None:
    if not task.knowledge_base_id:
        return None
    related = repo.list(
        tenant_id,
        knowledge_base_id=task.knowledge_base_id,
    )
    related = [item for item in related if item.task_type == task.task_type]
    counts = {"queued": 0, "processing": 0, "completed": 0, "failed": 0}
    failures: list[ProcessingTaskFailure] = []
    for item in related:
        if item.status in counts:
            counts[item.status] += 1
        if item.status == "failed" and item.error_message:
            failures.append(
                ProcessingTaskFailure(
                    task_id=item.id,
                    document_id=item.document_id,
                    error_message=item.error_message,
                )
            )
    return ProcessingTaskBatchSummary(
        total=len(related),
        queued=counts["queued"],
        processing=counts["processing"],
        completed=counts["completed"],
        failed=counts["failed"],
        failures=failures,
    )
