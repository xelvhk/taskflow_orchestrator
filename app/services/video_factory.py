from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.services.summarization import NonRetryableTaskError, RetryableTaskError


class VideoFactoryRender(BaseModel):
    status: str = Field(min_length=1)
    url: str | None = None


class VideoFactoryResult(BaseModel):
    project_id: str = Field(min_length=1)
    script: dict[str, Any]
    render: VideoFactoryRender
    warnings: list[str] = Field(default_factory=list)


@dataclass
class VideoFactoryAdapter:
    webhook_url: str | None = None
    timeout_seconds: float | None = None

    def create_draft(self, payload: dict[str, Any]) -> dict[str, object]:
        if self.webhook_url is None:
            self.webhook_url = settings.video_factory_webhook_url
        if self.timeout_seconds is None:
            self.timeout_seconds = settings.video_factory_timeout_seconds
        if not self.webhook_url:
            raise NonRetryableTaskError("Video factory webhook URL is not configured.")

        body = json.dumps(payload["brief"]).encode("utf-8")
        request = Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code >= 500:
                raise RetryableTaskError(f"Video factory unavailable: HTTP {exc.code}") from exc
            raise NonRetryableTaskError(f"Video factory rejected request: HTTP {exc.code}") from exc
        except (TimeoutError, URLError) as exc:
            raise RetryableTaskError("Video factory unavailable.") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NonRetryableTaskError("Invalid video factory response: not JSON.") from exc
        return validate_video_factory_response(decoded)


def validate_video_factory_response(payload: dict[str, Any]) -> dict[str, object]:
    try:
        result = VideoFactoryResult.model_validate(payload)
    except ValidationError as exc:
        raise NonRetryableTaskError("Invalid video factory response.") from exc
    return result.model_dump()


class SuccessfulVideoFactoryAdapter:
    def create_draft(self, payload: dict[str, Any]) -> dict[str, object]:
        return {
            "project_id": "vf_001",
            "script": {"hook": "Open with the portfolio proof."},
            "render": {"status": "succeeded", "url": "https://example.com/draft.mp4"},
            "warnings": [],
        }


class RetryableVideoFactoryAdapter:
    def create_draft(self, payload: dict[str, Any]) -> dict[str, object]:
        raise RetryableTaskError("Video factory unavailable.")


class MalformedVideoFactoryAdapter:
    def create_draft(self, payload: dict[str, Any]) -> dict[str, object]:
        return validate_video_factory_response({"project_id": "", "render": {}})
