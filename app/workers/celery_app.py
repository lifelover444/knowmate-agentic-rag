from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "knowmate",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)
