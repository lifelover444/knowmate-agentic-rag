from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProcessingTask


class ProcessingTaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, task: ProcessingTask) -> ProcessingTask:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: str, tenant_id: int | None = None) -> ProcessingTask | None:
        query = select(ProcessingTask).where(ProcessingTask.id == task_id)
        if tenant_id is not None:
            query = query.where(ProcessingTask.tenant_id == tenant_id)
        return self.db.scalar(query)

    def list(
        self,
        tenant_id: int,
        *,
        knowledge_base_id: str | None = None,
        document_id: str | None = None,
        status: str | None = None,
    ) -> list[ProcessingTask]:
        query = select(ProcessingTask).where(ProcessingTask.tenant_id == tenant_id)
        if knowledge_base_id:
            query = query.where(ProcessingTask.knowledge_base_id == knowledge_base_id)
        if document_id:
            query = query.where(ProcessingTask.document_id == document_id)
        if status:
            query = query.where(ProcessingTask.status == status)
        query = query.order_by(ProcessingTask.created_at.desc(), ProcessingTask.id.desc())
        return list(self.db.scalars(query).all())

    def latest_for_document(self, document_id: str, task_types: set[str] | None = None) -> ProcessingTask | None:
        query = select(ProcessingTask).where(
            ProcessingTask.document_id == document_id,
            ProcessingTask.status.in_(["queued", "processing"]),
        )
        if task_types:
            query = query.where(ProcessingTask.task_type.in_(task_types))
        query = query.order_by(ProcessingTask.created_at.desc(), ProcessingTask.id.desc())
        return self.db.scalar(query)

    def save(self, task: ProcessingTask) -> ProcessingTask:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_processing(self, task: ProcessingTask) -> ProcessingTask:
        task.status = "processing"
        task.progress = max(task.progress, 10)
        task.started_at = task.started_at or datetime.now(UTC)
        task.finished_at = None
        task.error_message = None
        return self.save(task)

    def mark_completed(self, task: ProcessingTask) -> ProcessingTask:
        task.status = "completed"
        task.progress = 100
        task.finished_at = datetime.now(UTC)
        task.error_message = None
        return self.save(task)

    def mark_failed(self, task: ProcessingTask, error_message: str) -> ProcessingTask:
        task.status = "failed"
        task.finished_at = datetime.now(UTC)
        task.error_message = error_message
        return self.save(task)

    def mark_cancelled(self, task: ProcessingTask, error_message: str = "用户已取消解析") -> ProcessingTask:
        task.status = "cancelled"
        task.finished_at = datetime.now(UTC)
        task.error_message = error_message
        return self.save(task)

    def cancel_active_for_document(
        self,
        document_id: str,
        error_message: str = "用户已取消解析",
    ) -> list[ProcessingTask]:
        tasks = list(
            self.db.scalars(
                select(ProcessingTask).where(
                    ProcessingTask.document_id == document_id,
                    ProcessingTask.status.in_(["queued", "processing"]),
                )
            ).all()
        )
        for task in tasks:
            task.status = "cancelled"
            task.finished_at = datetime.now(UTC)
            task.error_message = error_message
            self.db.add(task)
        self.db.commit()
        return tasks
