UV_CACHE_DIR ?= .uv-cache

.PHONY: install lint test check migrate run-api run-worker compose-up compose-down create-key smoke

install:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync

lint:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run ruff check .

test:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest

check: lint test

migrate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run alembic upgrade head

run-api:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run uvicorn app.main:app --reload

run-worker:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info

compose-up:
	cp -n .env.example .env || true
	docker compose up --build

compose-down:
	docker compose down

create-key:
	docker compose exec api python -m app.cli create-api-key --name demo

smoke:
	bash scripts/smoke_test.sh
