from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    api_key_pepper: str = Field(default="dev-only-pepper", min_length=8)
    database_url: str = "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    default_max_retries: int = Field(default=3, ge=0, le=10)
    retry_base_delay_seconds: int = Field(default=5, ge=1, le=3600)
    video_factory_webhook_url: str | None = None
    video_factory_timeout_seconds: float = Field(default=15, ge=1, le=120)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
