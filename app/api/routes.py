from typing import Annotated

from fastapi import APIRouter, Header, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import CreateTaskRequest, TaskListResponse, TaskResponse
from app.db.models import TaskStatus
from app.services.tasks import TaskService
from app.workers.tasks import enqueue_summarize_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
def create_task(
    request: CreateTaskRequest,
    session: DbSession,
    current_user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TaskResponse:
    return TaskService(session, enqueue_task=enqueue_summarize_task).create_task(
        user=current_user,
        request=request,
        idempotency_key=idempotency_key,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, session: DbSession, current_user: CurrentUser) -> TaskResponse:
    return TaskService(session).get_task(user=current_user, task_id=task_id)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    session: DbSession,
    current_user: CurrentUser,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaskListResponse:
    return TaskService(session).list_tasks(
        user=current_user,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: str, session: DbSession, current_user: CurrentUser) -> TaskResponse:
    return TaskService(session).cancel_task(user=current_user, task_id=task_id)
