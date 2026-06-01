from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import TaskStatus, TaskType


class SummarizeTextPayload(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank.")
        return value


class VideoBrief(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    audience: str = Field(min_length=1, max_length=200)
    cta: str = Field(min_length=1, max_length=200)
    language: str = Field(default="ru", min_length=2, max_length=16)
    target_platform: str = Field(default="youtube_shorts", max_length=80)
    duration_sec: int = Field(default=60, ge=15, le=180)
    tone: str = Field(default="expert, concise", min_length=1, max_length=200)
    format: str = Field(default="9:16", min_length=1, max_length=32)
    review_required: bool = True

    @field_validator("topic", "audience", "cta", "tone")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value


class VideoDraftPayload(BaseModel):
    source: str = Field(default="api", min_length=1, max_length=80)
    telegram: dict[str, str] = Field(default_factory=dict)
    brief: VideoBrief
    discussion: dict[str, Any] = Field(default_factory=dict)
    tool: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRequest(BaseModel):
    type: TaskType
    payload: SummarizeTextPayload | VideoDraftPayload
    max_retries: int | None = Field(default=None, ge=0, le=10)

    @model_validator(mode="after")
    def payload_must_match_type(self) -> "CreateTaskRequest":
        if self.type == TaskType.SUMMARIZE_TEXT and not isinstance(
            self.payload, SummarizeTextPayload
        ):
            raise ValueError("summarize_text tasks require a text payload.")
        if self.type == TaskType.VIDEO_DRAFT and not isinstance(self.payload, VideoDraftPayload):
            raise ValueError("video_draft tasks require a video draft payload.")
        return self


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
