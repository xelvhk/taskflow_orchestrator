from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from app.api.dependencies import DbSession
from app.api.errors import install_error_handlers
from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.metrics import MetricsService


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Taskflow Orchestrator",
        version="0.1.0",
        description="Reliable async task orchestration API with Celery retries and task history.",
    )
    install_error_handlers(app)
    app.include_router(router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.app_env}

    @app.get("/ready", tags=["health"])
    def ready(session: DbSession) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/metrics", response_class=PlainTextResponse, tags=["observability"])
    def metrics(session: DbSession) -> PlainTextResponse:
        return PlainTextResponse(
            MetricsService(session).render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()
