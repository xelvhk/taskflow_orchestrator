import logging
import socket

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.tasks import TaskExecutionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def enqueue_summarize_task(task_id: str) -> None:
    execute_summarize_task.delay(task_id)


@celery_app.task(name="tasks.execute_summarize_task", bind=True)
def execute_summarize_task(self, task_id: str) -> None:
    redis_client = Redis.from_url(settings.redis_url)
    lock_key = f"taskflow:task-lock:{task_id}"
    lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=300)
    if not lock_acquired:
        logger.info("task_lock_already_held", extra={"task_id": task_id})
        return

    session: Session = SessionLocal()
    try:
        delay = TaskExecutionService(
            session,
            worker_name=socket.gethostname(),
        ).execute_once(task_id)
        if delay is not None:
            self.apply_async(args=[task_id], countdown=delay)
    finally:
        session.close()
        redis_client.delete(lock_key)
