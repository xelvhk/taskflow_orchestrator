from fastapi.testclient import TestClient


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"


def test_tasks_require_api_key(client: TestClient) -> None:
    response = client.get("/tasks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_create_get_and_list_task(client: TestClient, api_key: str) -> None:
    response = client.post(
        "/tasks",
        headers={"X-API-Key": api_key, "Idempotency-Key": "article-1"},
        json={
            "type": "summarize_text",
            "payload": {"text": "This is a useful article that should be summarized."},
            "max_retries": 2,
        },
    )

    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "queued"
    assert created["max_retries"] == 2

    get_response = client.get(f"/tasks/{created['id']}", headers={"X-API-Key": api_key})
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    list_response = client.get("/tasks?status=queued", headers={"X-API-Key": api_key})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == created["id"]


def test_create_task_idempotency_returns_existing_task(client: TestClient, api_key: str) -> None:
    payload = {
        "type": "summarize_text",
        "payload": {"text": "same request"},
    }

    first = client.post(
        "/tasks",
        headers={"X-API-Key": api_key, "Idempotency-Key": "same-key"},
        json=payload,
    )
    second = client.post(
        "/tasks",
        headers={"X-API-Key": api_key, "Idempotency-Key": "same-key"},
        json=payload,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


def test_create_video_draft_task(client: TestClient, api_key: str) -> None:
    response = client.post(
        "/tasks",
        headers={"X-API-Key": api_key, "Idempotency-Key": "video-1"},
        json={
            "type": "video_draft",
            "payload": {
                "source": "telegram",
                "telegram": {"chat_id": "42", "user_id": "7"},
                "brief": {
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
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["type"] == "video_draft"
    assert response.json()["payload"]["brief"]["topic"] == "ai-video-factory portfolio"


def test_cancel_queued_task(client: TestClient, api_key: str) -> None:
    created = client.post(
        "/tasks",
        headers={"X-API-Key": api_key},
        json={"type": "summarize_text", "payload": {"text": "cancel me"}},
    ).json()

    response = client.post(f"/tasks/{created['id']}/cancel", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_missing_task_returns_404(client: TestClient, api_key: str) -> None:
    response = client.post("/tasks/missing/cancel", headers={"X-API-Key": api_key})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_replay_rejects_non_dead_letter_task(client: TestClient, api_key: str) -> None:
    created = client.post(
        "/tasks",
        headers={"X-API-Key": api_key},
        json={"type": "summarize_text", "payload": {"text": "not dead letter"}},
    ).json()

    response = client.post(f"/tasks/{created['id']}/replay", headers={"X-API-Key": api_key})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TASK_NOT_REPLAYABLE"
