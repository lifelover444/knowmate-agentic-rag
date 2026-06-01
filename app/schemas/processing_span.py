from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingSpanRead(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: str
    status: str
    input: dict | None = None
    output: dict | None = None
    metadata: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0


class ProcessingSpanTimeline(BaseModel):
    knowledge_id: str
    attempt: int
    root: ProcessingSpanRead
    stages: list[ProcessingSpanRead] = Field(default_factory=list)
