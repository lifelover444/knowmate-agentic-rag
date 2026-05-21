from app.core.config import get_settings
from app.db.session import make_session_factory
from app.integrations.llm_openai import OpenAIEmbedder
from app.integrations.qdrant_store import QdrantVectorStore
from app.services.document_processing import DocumentProcessingService
from app.workers.celery_app import celery_app


def enqueue_document_processing(document_id: str) -> None:
    process_document.delay(document_id)


@celery_app.task(name="documents.process")
def process_document(document_id: str) -> None:
    settings = get_settings()
    session_factory = make_session_factory(settings)
    with session_factory() as db:
        DocumentProcessingService(
            db=db,
            upload_dir=settings.upload_dir,
            embedder=OpenAIEmbedder(settings),
            vector_store=QdrantVectorStore(settings),
        ).process(document_id)
