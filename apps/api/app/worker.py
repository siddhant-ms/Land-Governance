"""Optional Celery worker: `celery -A app.worker worker -l info` (JOB_BACKEND=celery, REDIS_URL set)."""
import uuid

from celery import Celery

from app.core.config import get_settings
from app.services.ingestion.pipeline import process_job

_s = get_settings()
celery_app = Celery("sih26019", broker=_s.redis_url or "redis://localhost:6379/0",
                    backend=_s.redis_url or "redis://localhost:6379/0")


@celery_app.task(name="ingest_document")
def ingest_task(job_id: str) -> None:
    process_job(uuid.UUID(job_id))
