from sqlalchemy.orm import Session

from app.api.schemas import CreateTaskRequest, SummarizeTextPayload
from app.db.models import TaskStatus, TaskType, User
from app.services.tasks import TaskExecutionService, TaskService, retry_delay_seconds


def test_create_task_is_idempotent_for_same_user_and_key(session: Session, user: User) -> None:
    enqueued: list[str] = []
    service = TaskService(session, enqueue_task=enqueued.append)
    request = CreateTaskRequest(
        type=TaskType.SUMMARIZE_TEXT,
        payload=SummarizeTextPayload(text="A concise piece of text."),
        max_retries=2,
    )

    first = service.create_task(user=user, request=request, idempotency_key="same-key")
    second = service.create_task(user=user, request=request, idempotency_key="same-key")

    assert first.id == second.id
    assert enqueued == [first.id]


def test_retry_delay_uses_exponential_backoff() -> None:
    assert retry_delay_seconds(0) == 5
    assert retry_delay_seconds(1) == 10
    assert retry_delay_seconds(2) == 20


def test_execute_task_success_writes_result_and_attempt(session: Session, user: User) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.SUMMARIZE_TEXT,
            payload=SummarizeTextPayload(text="one two three four"),
            max_retries=1,
        ),
        idempotency_key=None,
    )

    delay = TaskExecutionService(session, worker_name="worker-1").execute_once(task.id)
    session.refresh(task)

    assert delay is None
    assert task.status == TaskStatus.SUCCEEDED
    assert task.result == {"summary": "one two three four", "input_words": 4, "summary_words": 4}
    assert len(task.attempts) == 1
    assert task.attempts[0].status == TaskStatus.SUCCEEDED


def test_execute_task_retryable_failure_moves_to_retrying(session: Session, user: User) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.SUMMARIZE_TEXT,
            payload=SummarizeTextPayload(text="please __retry__ once"),
            max_retries=2,
        ),
        idempotency_key=None,
    )

    delay = TaskExecutionService(session, worker_name="worker-1").execute_once(task.id)
    session.refresh(task)

    assert delay == 5
    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 1
    assert task.next_retry_at is not None
    assert task.attempts[0].status == TaskStatus.RETRYING


def test_execute_task_exhausted_retries_moves_to_dead_letter(
    session: Session, user: User
) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.SUMMARIZE_TEXT,
            payload=SummarizeTextPayload(text="please __retry__ forever"),
            max_retries=0,
        ),
        idempotency_key=None,
    )

    delay = TaskExecutionService(session, worker_name="worker-1").execute_once(task.id)
    session.refresh(task)

    assert delay is None
    assert task.status == TaskStatus.DEAD_LETTER
    assert task.retry_count == 0
    assert task.completed_at is not None
    assert task.attempts[0].status == TaskStatus.DEAD_LETTER


def test_non_retryable_failure_moves_to_failed(session: Session, user: User) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.SUMMARIZE_TEXT,
            payload=SummarizeTextPayload(text="please __fail__ now"),
            max_retries=3,
        ),
        idempotency_key=None,
    )

    TaskExecutionService(session, worker_name="worker-1").execute_once(task.id)
    session.refresh(task)

    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 0
    assert task.attempts[0].status == TaskStatus.FAILED
