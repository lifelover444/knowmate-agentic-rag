from app.core.config import Settings
from app.db.models import Knowledge, ProcessingTask
from app.db.repositories.task import ProcessingTaskRepository

TASK_DOCUMENT_UPLOAD_PROCESS = "document_upload_process"
TASK_DOCUMENT_REPROCESS = "document_reprocess"
TASK_KNOWLEDGE_BASE_REBUILD = "knowledge_base_rebuild"

TASK_TYPES = {
    TASK_DOCUMENT_UPLOAD_PROCESS,
    TASK_DOCUMENT_REPROCESS,
    TASK_KNOWLEDGE_BASE_REBUILD,
}

TASK_STATUSES = {"queued", "processing", "completed", "failed", "cancelled"}


class ProcessingTaskService:
    def __init__(self, repo: ProcessingTaskRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def create_for_document(self, document: Knowledge, task_type: str) -> ProcessingTask:
        if task_type not in TASK_TYPES:
            raise ValueError("不支持的任务类型")
        return self.repo.create(
            ProcessingTask(
                tenant_id=document.tenant_id,
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
                task_type=task_type,
                status="queued",
                progress=0,
            )
        )

    def retry(self, task: ProcessingTask) -> ProcessingTask:
        if task.status != "failed":
            raise ValueError("只有失败任务可以重试")
        task.status = "queued"
        task.progress = 0
        task.error_message = None
        task.started_at = None
        task.finished_at = None
        return self.repo.save(task)
