from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingTaskFailure(BaseModel):
    task_id: str
    document_id: str | None
    error_message: str


class ProcessingTaskBatchSummary(BaseModel):
    total: int = 0
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    failures: list[ProcessingTaskFailure] = Field(default_factory=list)


class ProcessingTaskRead(BaseModel):
    id: str
    tenant_id: int
    knowledge_base_id: str | None
    document_id: str | None
    task_type: str
    status: str
    progress: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    batch_summary: ProcessingTaskBatchSummary | None = None

    model_config = {"from_attributes": True}
