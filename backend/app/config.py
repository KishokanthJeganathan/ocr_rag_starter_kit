"""Environment-driven application settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"

    # Application DB role is RLS-enforced (see infra/postgres/init.sql).
    # Host port 5433 -> compose Postgres (5432 is left for a native install).
    database_url: str = "postgresql+psycopg://ocr_app:ocr_app@localhost:5433/ocr_rag"

    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = "http://localhost:9000"  # empty string -> real AWS S3
    s3_region: str = "us-east-1"
    s3_bucket: str = "ocr-rag-documents"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin"

    max_upload_bytes: int = 25 * 1024 * 1024

    # Populated in later stages.
    azure_di_endpoint: str | None = None
    azure_di_key: str | None = None
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


settings = Settings()
