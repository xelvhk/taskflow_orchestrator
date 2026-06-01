from sqlalchemy.orm import Session

from app.api.schemas import CreateTaskRequest, SummarizeTextPayload, VideoDraftPayload
from app.db.models import TaskStatus, TaskType, User
from app.services.tasks import TaskExecutionService, TaskService, retry_delay_seconds
from app.services.video_factory import (
    MalformedVideoFactoryAdapter,
    RetryableVideoFactoryAdapter,
    SuccessfulVideoFactoryAdapter,
)


def video_payload() -> VideoDraftPayload:
    return VideoDraftPayload(
        source="telegram",
        telegram={"chat_id": "42", "user_id": "7"},
        brief={
            "topic": "ai-video-factory portfolio",
            "audience": "portfolio reviewers",
            "cta": "subscribe",
            "language": "en",
            "target_platform": "youtube_shorts",
            "duration_sec": 60,
            "tone": "expert, practical",
            "format": "9:16",
            "review_required": True,
        },
        discussion={"steps": []},
        tool={"agent_role": "VIDEO_PRODUCER", "adapter": "ai-video-factory"},
    )


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


def test_create_video_draft_task_preserves_type_and_payload(
    session: Session,
    user: User,
) -> None:
    enqueued: list[str] = []
    service = TaskService(session, enqueue_task=enqueued.append)
    request = CreateTaskRequest(
        type=TaskType.VIDEO_DRAFT,
        payload=video_payload(),
        max_retries=2,
    )

    task = service.create_task(user=user, request=request, idempotency_key="video-1")

    assert task.type == TaskType.VIDEO_DRAFT
    assert task.payload["brief"]["topic"] == "ai-video-factory portfolio"
    assert enqueued == [task.id]


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


def test_execute_video_draft_success_writes_result_and_attempt(
    session: Session,
    user: User,
) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.VIDEO_DRAFT,
            payload=video_payload(),
            max_retries=1,
        ),
        idempotency_key=None,
    )

    delay = TaskExecutionService(
        session,
        video_factory_adapter=SuccessfulVideoFactoryAdapter(),
        worker_name="worker-1",
    ).execute_once(task.id)
    session.refresh(task)

    assert delay is None
    assert task.status == TaskStatus.SUCCEEDED
    assert task.result == {
        "project_id": "vf_001",
        "script": {"hook": "Open with the portfolio proof."},
        "render": {"status": "succeeded", "url": "https://example.com/draft.mp4"},
        "warnings": [],
    }
    assert task.attempts[0].status == TaskStatus.SUCCEEDED


def test_execute_video_draft_retryable_failure_moves_to_retrying(
    session: Session,
    user: User,
) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.VIDEO_DRAFT,
            payload=video_payload(),
            max_retries=2,
        ),
        idempotency_key=None,
    )

    delay = TaskExecutionService(
        session,
        video_factory_adapter=RetryableVideoFactoryAdapter(),
        worker_name="worker-1",
    ).execute_once(task.id)
    session.refresh(task)

    assert delay == 5
    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 1
    assert task.attempts[0].status == TaskStatus.RETRYING


def test_execute_video_draft_malformed_response_moves_to_failed(
    session: Session,
    user: User,
) -> None:
    task = TaskService(session).create_task(
        user=user,
        request=CreateTaskRequest(
            type=TaskType.VIDEO_DRAFT,
            payload=video_payload(),
            max_retries=2,
        ),
        idempotency_key=None,
    )

    TaskExecutionService(
        session,
        video_factory_adapter=MalformedVideoFactoryAdapter(),
        worker_name="worker-1",
    ).execute_once(task.id)
    session.refresh(task)

    assert task.status == TaskStatus.FAILED
    assert task.error is not None
    assert "Invalid video factory response" in task.error


def test_replay_dead_letter_task_resets_runtime_state_and_enqueues(
    session: Session,
    user: User,
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
    TaskExecutionService(session, worker_name="worker-1").execute_once(task.id)
    session.refresh(task)
    assert task.status == TaskStatus.DEAD_LETTER

    enqueued: list[str] = []
    replayed = TaskService(session, enqueue_task=enqueued.append).replay_task(
        user=user,
        task_id=task.id,
    )

    assert replayed.status == TaskStatus.QUEUED
    assert replayed.retry_count == 0
    assert replayed.error is None
    assert replayed.result is None
    assert replayed.next_retry_at is None
    assert replayed.completed_at is None
    assert enqueued == [task.id]
