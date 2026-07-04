from app.core.config import get_settings
from app.db.repositories.task import ProcessingTaskRepository
from app.db.session import make_session_factory
from app.integrations.vector_store import VectorStoreRegistry
from app.services.document_processing import DocumentProcessingCancelled, DocumentProcessingService
from app.services.evaluation import EvaluationService
from app.services.task import TASK_DOCUMENT_REPROCESS, TASK_DOCUMENT_UPLOAD_PROCESS, TASK_KNOWLEDGE_BASE_REBUILD
from app.workers.celery_app import celery_app


def enqueue_document_processing(document_id: str) -> None:
    process_document.delay(document_id)


def enqueue_evaluation_run(run_id: str) -> None:
    run_evaluation.delay(run_id)


@celery_app.task(name="documents.process")
def process_document(document_id: str) -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    with session_factory() as db:
        task_repo = ProcessingTaskRepository(db)
        task = task_repo.latest_for_document(
            document_id,
            {
                TASK_DOCUMENT_UPLOAD_PROCESS,
                TASK_DOCUMENT_REPROCESS,
                TASK_KNOWLEDGE_BASE_REBUILD,
            },
        )
        if task is not None:
            task_repo.mark_processing(task)
        try:
            DocumentProcessingService(
                db=db,
                upload_dir=settings.upload_dir,
                settings=settings,
                vector_store=VectorStoreRegistry(settings).build("qdrant"),
            ).process(document_id)
        except DocumentProcessingCancelled as exc:
            if task is not None:
                task_repo.mark_cancelled(task, str(exc))
            return
        except Exception as exc:
            if task is not None:
                task_repo.mark_failed(task, str(exc))
            raise
        if task is not None:
            task_repo.mark_completed(task)


@celery_app.task(name="evaluations.run")
def run_evaluation(run_id: str) -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    with session_factory() as db:
        service = EvaluationService(
            db,
            settings,
            vector_store=VectorStoreRegistry(settings).build("qdrant"),
        )
        try:
            service.run_evaluation(run_id)
        except Exception as exc:
            db.rollback()
            service.mark_failed(run_id, str(exc))
            raise
