from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.api.schemas import CreateTaskRequest, TaskListResponse
from app.core.config import settings
from app.db.models import Task, TaskAttempt, TaskStatus, TaskType, User
from app.db.repositories import TaskRepository
from app.services.summarization import (
    NonRetryableTaskError,
    RetryableTaskError,
    SummarizationAdapter,
)
from app.services.video_factory import VideoFactoryAdapter

EnqueueTask = Callable[[str], None]

TERMINAL_STATUSES = {
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.DEAD_LETTER,
    TaskStatus.CANCELLED,
}


def retry_delay_seconds(retry_count: int) -> int:
    return settings.retry_base_delay_seconds * (2**retry_count)


class TaskService:
    def __init__(self, session: Session, enqueue_task: EnqueueTask | None = None) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.enqueue_task = enqueue_task

    def create_task(
        self,
        *,
        user: User,
        request: CreateTaskRequest,
        idempotency_key: str | None,
    ) -> Task:
        if idempotency_key:
            existing = self.tasks.get_by_idempotency_key(
                user_id=user.id, idempotency_key=idempotency_key
            )
            if existing is not None:
                return existing

        max_retries = request.max_retries
        if max_retries is None:
            max_retries = settings.default_max_retries

        task = self.tasks.create(
            Task(
                user_id=user.id,
                type=request.type,
                status=TaskStatus.QUEUED,
                payload=request.payload.model_dump(),
                max_retries=max_retries,
                retry_count=0,
                idempotency_key=idempotency_key,
            )
        )
        self.session.commit()
        self.session.refresh(task)

        if self.enqueue_task is not None:
            self.enqueue_task(task.id)
        return task

    def get_task(self, *, user: User, task_id: str) -> Task:
        task = self.tasks.get_for_user(task_id=task_id, user_id=user.id)
        if task is None:
            raise APIError(status_code=404, code="TASK_NOT_FOUND", message="Task not found.")
        return task

    def list_tasks(
        self,
        *,
        user: User,
        status: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> TaskListResponse:
        items = self.tasks.list_for_user(
            user_id=user.id,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = self.tasks.count_for_user(user_id=user.id, status=status)
        return TaskListResponse(items=items, total=total, limit=limit, offset=offset)

    def cancel_task(self, *, user: User, task_id: str) -> Task:
        task = self.get_task(user=user, task_id=task_id)
        if task.status not in {TaskStatus.QUEUED, TaskStatus.RETRYING}:
            raise APIError(
                status_code=409,
                code="TASK_NOT_CANCELLABLE",
                message="Only queued or retrying tasks can be cancelled.",
            )
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(task)
        return task

    def replay_task(self, *, user: User, task_id: str) -> Task:
        task = self.get_task(user=user, task_id=task_id)
        if task.status != TaskStatus.DEAD_LETTER:
            raise APIError(
                status_code=409,
                code="TASK_NOT_REPLAYABLE",
                message="Only dead-letter tasks can be replayed.",
            )

        task.status = TaskStatus.QUEUED
        task.error = None
        task.result = None
        task.retry_count = 0
        task.next_retry_at = None
        task.completed_at = None
        self.session.commit()
        self.session.refresh(task)

        if self.enqueue_task is not None:
            self.enqueue_task(task.id)
        return task


class TaskExecutionService:
    def __init__(
        self,
        session: Session,
        adapter: SummarizationAdapter | None = None,
        video_factory_adapter: VideoFactoryAdapter | None = None,
        worker_name: str | None = None,
    ) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.summarization_adapter = adapter or SummarizationAdapter()
        self.video_factory_adapter = video_factory_adapter or VideoFactoryAdapter()
        self.worker_name = worker_name

    def execute_once(self, task_id: str) -> int | None:
        task = self.tasks.get_by_id(task_id)
        if task is None or task.status in TERMINAL_STATUSES:
            return None

        now = datetime.now(UTC)
        task.status = TaskStatus.RUNNING
        task.error = None
        attempt = self.tasks.add_attempt(
            TaskAttempt(
                task_id=task.id,
                attempt_number=task.retry_count + 1,
                status=TaskStatus.RUNNING,
                started_at=now,
                worker_name=self.worker_name,
            )
        )
        self.session.commit()

        started_at = datetime.now(UTC)
        try:
            result = self._execute_task_payload(task)
        except RetryableTaskError as exc:
            return self._handle_retryable_error(task, attempt, str(exc), started_at)
        except (NonRetryableTaskError, KeyError, TypeError) as exc:
            self._finish_failed(task, attempt, str(exc), started_at)
            return None

        finished_at = datetime.now(UTC)
        attempt.status = TaskStatus.SUCCEEDED
        attempt.finished_at = finished_at
        attempt.duration_ms = elapsed_ms(started_at, finished_at)
        task.status = TaskStatus.SUCCEEDED
        task.result = result
        task.error = None
        task.next_retry_at = None
        task.completed_at = finished_at
        self.session.commit()
        return None

    def _execute_task_payload(self, task: Task) -> dict[str, object]:
        if task.type == TaskType.SUMMARIZE_TEXT:
            return self.summarization_adapter.summarize(str(task.payload["text"]))
        if task.type == TaskType.VIDEO_DRAFT:
            return self.video_factory_adapter.create_draft(task.payload)
        raise NonRetryableTaskError(f"Unsupported task type: {task.type}")

    def _handle_retryable_error(
        self,
        task: Task,
        attempt: TaskAttempt,
        error: str,
        started_at: datetime,
    ) -> int | None:
        finished_at = datetime.now(UTC)
        attempt.error = error
        attempt.finished_at = finished_at
        attempt.duration_ms = elapsed_ms(started_at, finished_at)

        if task.retry_count >= task.max_retries:
            attempt.status = TaskStatus.DEAD_LETTER
            task.status = TaskStatus.DEAD_LETTER
            task.error = error
            task.completed_at = finished_at
            task.next_retry_at = None
            self.session.commit()
            return None

        delay_seconds = retry_delay_seconds(task.retry_count)
        task.retry_count += 1
        attempt.status = TaskStatus.RETRYING
        task.status = TaskStatus.RETRYING
        task.error = error
        task.next_retry_at = finished_at + timedelta(seconds=delay_seconds)
        self.session.commit()
        return delay_seconds

    def _finish_failed(
        self,
        task: Task,
        attempt: TaskAttempt,
        error: str,
        started_at: datetime,
    ) -> None:
        finished_at = datetime.now(UTC)
        attempt.status = TaskStatus.FAILED
        attempt.error = error
        attempt.finished_at = finished_at
        attempt.duration_ms = elapsed_ms(started_at, finished_at)
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = finished_at
        task.next_retry_at = None
        self.session.commit()


def elapsed_ms(started_at: datetime, finished_at: datetime) -> int:
    return int((finished_at - started_at).total_seconds() * 1000)
