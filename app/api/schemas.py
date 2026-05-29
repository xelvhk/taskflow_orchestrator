from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import TaskStatus, TaskType


class SummarizeTextPayload(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank.")
        return value


class CreateTaskRequest(BaseModel):
    type: Literal[TaskType.SUMMARIZE_TEXT]
    payload: SummarizeTextPayload
    max_retries: int | None = Field(default=None, ge=0, le=10)


class AttemptResponse(BaseModel):
    id: str
    attempt_number: int
    status: TaskStatus
    error: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    worker_name: str | None

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    attempts: list[AttemptResponse]

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    limit: int
    offset: int
