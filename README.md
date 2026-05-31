# Taskflow Orchestrator

[Русская версия](README.ru.md)

Production-style FastAPI backend for reliable async task orchestration. The MVP exposes an API for creating `summarize_text` jobs, executes them in Celery workers, persists status/result/history in PostgreSQL, and uses Redis for broker/locks.

## Why This Project Matters

This project demonstrates backend skills that matter in real systems: API design, durable state transitions, idempotency, background execution, retry/backoff, dead-letter handling, Dockerized infrastructure, and testable service boundaries.

## Architecture

```mermaid
flowchart LR
    Client[API client] -->|X-API-Key| API[FastAPI]
    API --> DB[(PostgreSQL)]
    API -->|enqueue task id| Redis[(Redis broker)]
    Redis --> Worker[Celery worker]
    Worker --> DB
    Worker -->|retry countdown| Redis
    Beat[Celery beat] --> Redis
```

PostgreSQL is the source of truth for task status, results, errors, and attempt history. Redis is runtime infrastructure only: Celery broker plus short-lived task locks.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

In another terminal, create a demo API key:

```bash
docker compose exec api python -m app.cli create-api-key --name demo
```

Use the printed key:

```bash
API_KEY="tf_..."

curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "Idempotency-Key: article-001" \
  -d '{"type":"summarize_text","payload":{"text":"Taskflow turns slow work into reliable background jobs with retries."},"max_retries":3}'
```

Check status:

```bash
curl http://localhost:8000/tasks/{task_id} -H "X-API-Key: $API_KEY"
```

Or run the end-to-end smoke test after the stack is up:

```bash
make smoke
```

## API

- `GET /health` - process health.
- `GET /ready` - database readiness check.
- `POST /tasks` - create a task and enqueue it.
- `GET /tasks/{id}` - get status, result, error, and attempts.
- `GET /tasks?status=queued&limit=20&offset=0` - list tasks.
- `POST /tasks/{id}/cancel` - cancel `queued` or `retrying` tasks.
- `POST /tasks/{id}/replay` - move a `dead_letter` task back to `queued`.

All `/tasks` endpoints require `X-API-Key`. `POST /tasks` supports `Idempotency-Key` to make retries safe.

## State Machine

```text
queued -> running -> succeeded
queued -> running -> retrying -> running
queued -> running -> failed
queued -> running -> dead_letter
queued/retrying -> cancelled
dead_letter -> queued
```

Retryable mock failures are triggered by including `__retry__` in the text. Non-retryable mock failures are triggered by `__fail__`.

## Local Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

The same workflow is available through Make:

```bash
make install
make check
```

Run only the API locally:

```bash
uv run uvicorn app.main:app --reload
```

Run migrations:

```bash
uv run alembic upgrade head
```

Run a worker:

```bash
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

## Design Trade-offs

- Real LLM integration is intentionally out of scope for v1. The summarization adapter is isolated so an OpenAI or local model adapter can be added later.
- Tests use SQLite for fast service/API coverage; Docker Compose is the integration path for PostgreSQL, Redis, Celery, and migrations.
- Celery result backend is not the business source of truth. Clients read status and results from PostgreSQL.

See [Architecture Notes](docs/ARCHITECTURE.md) for the boundary decisions, failure modes, and extension points.

## Next Steps

- Add OpenTelemetry traces and Prometheus metrics.
- Add PostgreSQL-backed scheduled jobs beyond retry countdowns.
- Add admin endpoints for dead-letter replay.
- Add a real LLM summarization adapter behind the existing interface.
