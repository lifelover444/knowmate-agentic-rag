from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
