from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Knowledge, KnowledgeProcessingSpan
from app.schemas.processing_span import ProcessingSpanRead, ProcessingSpanTimeline

PROCESSING_STAGES = ["parse", "chunk", "embed", "upsert", "finalize"]
_STAGE_ORDER = {name: index for index, name in enumerate(PROCESSING_STAGES)}


class ProcessingSpanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def open_attempt(self, document: Knowledge) -> int:
        attempt = self._next_attempt(document.id)
        now = datetime.now(UTC)
        rows = [
            KnowledgeProcessingSpan(
                tenant_id=document.tenant_id,
                knowledge_id=document.id,
                attempt=attempt,
                span_id="root",
                name="document_processing",
                kind="root",
                status="running",
                input_json={
                    "knowledge_base_id": document.knowledge_base_id,
                    "file_name": document.file_name,
                    "file_type": document.file_type,
                },
                started_at=now,
                duration_ms=0,
            )
        ]
        rows.extend(
            KnowledgeProcessingSpan(
                tenant_id=document.tenant_id,
                knowledge_id=document.id,
                attempt=attempt,
                span_id=name,
                parent_span_id="root",
                name=name,
                kind="stage",
                status="pending",
                duration_ms=0,
            )
            for name in PROCESSING_STAGES
        )
        self.db.add_all(rows)
        self.db.commit()
        return attempt

    def begin_stage(self, document_id: str, attempt: int, name: str, input_json: dict | None = None) -> None:
        span = self._stage(document_id, attempt, name)
        span.status = "running"
        span.started_at = datetime.now(UTC)
        span.finished_at = None
        span.duration_ms = 0
        span.input_json = input_json
        span.error_code = None
        span.error_message = None
        self.db.add(span)
        self.db.commit()

    def end_stage(self, document_id: str, attempt: int, name: str, output_json: dict | None = None) -> None:
        span = self._stage(document_id, attempt, name)
        finished_at = datetime.now(UTC)
        span.status = "done"
        span.finished_at = finished_at
        span.duration_ms = _duration_ms(span.started_at, finished_at)
        span.output_json = output_json
        self.db.add(span)
        self.db.commit()

    def fail_stage(self, document_id: str, attempt: int, name: str, exc: Exception) -> None:
        span = self._stage(document_id, attempt, name)
        finished_at = datetime.now(UTC)
        span.status = "failed"
        span.finished_at = finished_at
        span.duration_ms = _duration_ms(span.started_at, finished_at)
        span.error_code = exc.__class__.__name__
        span.error_message = str(exc)
        self.db.add(span)
        self._cancel_downstream(document_id, attempt, name)
        self.db.commit()

    def cancel_attempt(self, document_id: str, attempt: int, error_message: str = "用户已取消解析") -> None:
        rows = list(
            self.db.scalars(
                select(KnowledgeProcessingSpan).where(
                    KnowledgeProcessingSpan.knowledge_id == document_id,
                    KnowledgeProcessingSpan.attempt == attempt,
                    KnowledgeProcessingSpan.status.in_(["pending", "running"]),
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.status = "cancelled"
            row.finished_at = now
            row.duration_ms = _duration_ms(row.started_at, now)
            row.error_message = error_message if row.kind == "root" else None
            self.db.add(row)
        self.db.commit()

    def finalize_root(self, document_id: str, attempt: int, status: str, error_message: str | None = None) -> None:
        root = self._root(document_id, attempt)
        finished_at = datetime.now(UTC)
        root.status = status
        root.finished_at = finished_at
        root.duration_ms = _duration_ms(root.started_at, finished_at)
        root.error_message = error_message
        self.db.add(root)
        self.db.commit()

    def get_timeline(self, document_id: str) -> ProcessingSpanTimeline:
        document = self.db.scalar(select(Knowledge).where(Knowledge.id == document_id, Knowledge.deleted_at.is_(None)))
        if document is None:
            raise LookupError("document not found")
        attempt = self._latest_attempt(document_id)
        if attempt is None:
            return _placeholder_timeline(document)
        rows = list(
            self.db.scalars(
                select(KnowledgeProcessingSpan).where(
                    KnowledgeProcessingSpan.knowledge_id == document_id,
                    KnowledgeProcessingSpan.attempt == attempt,
                )
            ).all()
        )
        root = next((row for row in rows if row.kind == "root"), None)
        stages = sorted((row for row in rows if row.kind == "stage"), key=lambda row: _STAGE_ORDER.get(row.name, 999))
        if root is None:
            return _placeholder_timeline(document)
        return ProcessingSpanTimeline(
            knowledge_id=document_id,
            attempt=attempt,
            root=_to_read(root),
            stages=[_to_read(stage) for stage in stages],
        )

    def _next_attempt(self, document_id: str) -> int:
        latest = self._latest_attempt(document_id)
        return (latest or 0) + 1

    def _latest_attempt(self, document_id: str) -> int | None:
        return self.db.scalar(
            select(func.max(KnowledgeProcessingSpan.attempt)).where(KnowledgeProcessingSpan.knowledge_id == document_id)
        )

    def _root(self, document_id: str, attempt: int) -> KnowledgeProcessingSpan:
        span = self.db.scalar(
            select(KnowledgeProcessingSpan).where(
                KnowledgeProcessingSpan.knowledge_id == document_id,
                KnowledgeProcessingSpan.attempt == attempt,
                KnowledgeProcessingSpan.kind == "root",
            )
        )
        if span is None:
            raise LookupError("processing root span not found")
        return span

    def _stage(self, document_id: str, attempt: int, name: str) -> KnowledgeProcessingSpan:
        span = self.db.scalar(
            select(KnowledgeProcessingSpan).where(
                KnowledgeProcessingSpan.knowledge_id == document_id,
                KnowledgeProcessingSpan.attempt == attempt,
                KnowledgeProcessingSpan.kind == "stage",
                KnowledgeProcessingSpan.name == name,
            )
        )
        if span is None:
            raise LookupError(f"processing stage span not found: {name}")
        return span

    def _cancel_downstream(self, document_id: str, attempt: int, failed_name: str) -> None:
        failed_index = _STAGE_ORDER.get(failed_name, -1)
        if failed_index < 0:
            return
        rows = list(
            self.db.scalars(
                select(KnowledgeProcessingSpan).where(
                    KnowledgeProcessingSpan.knowledge_id == document_id,
                    KnowledgeProcessingSpan.attempt == attempt,
                    KnowledgeProcessingSpan.kind == "stage",
                    KnowledgeProcessingSpan.status.in_(["pending", "running"]),
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            if _STAGE_ORDER.get(row.name, -1) > failed_index:
                row.status = "cancelled"
                row.finished_at = now
                row.duration_ms = _duration_ms(row.started_at, now)
                self.db.add(row)


def _duration_ms(started_at: datetime | None, finished_at: datetime) -> int:
    if started_at is None:
        return 0
    start = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
    finish = finished_at if finished_at.tzinfo else finished_at.replace(tzinfo=UTC)
    return max(int((finish - start).total_seconds() * 1000), 0)


def _placeholder_timeline(document: Knowledge) -> ProcessingSpanTimeline:
    status = document.parse_status
    if status == "completed":
        root_status = "done"
        stage_statuses = ["done"] * len(PROCESSING_STAGES)
    elif status == "failed":
        root_status = "failed"
        stage_statuses = ["failed", "cancelled", "cancelled", "cancelled", "cancelled"]
    elif status == "processing":
        root_status = "running"
        stage_statuses = ["running", "pending", "pending", "pending", "pending"]
    elif status == "cancelled":
        root_status = "cancelled"
        stage_statuses = ["cancelled"] * len(PROCESSING_STAGES)
    else:
        root_status = "pending"
        stage_statuses = ["pending"] * len(PROCESSING_STAGES)
    root = ProcessingSpanRead(
        span_id="root",
        name="document_processing",
        kind="root",
        status=root_status,
        error_message=document.error_message,
        duration_ms=0,
    )
    stages = [
        ProcessingSpanRead(
            span_id=name,
            parent_span_id="root",
            name=name,
            kind="stage",
            status=stage_status,
            error_message=document.error_message if stage_status == "failed" else None,
            duration_ms=0,
        )
        for name, stage_status in zip(PROCESSING_STAGES, stage_statuses, strict=True)
    ]
    return ProcessingSpanTimeline(knowledge_id=document.id, attempt=0, root=root, stages=stages)


def _to_read(span: KnowledgeProcessingSpan) -> ProcessingSpanRead:
    return ProcessingSpanRead(
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        name=span.name,
        kind=span.kind,
        status=span.status,
        input=span.input_json,
        output=span.output_json,
        metadata=span.metadata_json,
        error_code=span.error_code,
        error_message=span.error_message,
        started_at=span.started_at,
        finished_at=span.finished_at,
        duration_ms=span.duration_ms,
    )
