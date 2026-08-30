"""Environment-driven application settings.

One ``.env`` at the repository root is the single source of config. Docker
Compose reads it for ``${VAR}`` interpolation; this app reads it directly (below)
for non-Docker runs.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"

    # Application DB role is RLS-enforced (see infra/postgres/init.sql).
    # Host port 5433 -> compose Postgres (5432 is left for a native install).
    database_url: str = "postgresql+psycopg://ocr_app:ocr_app@localhost:5433/ocr_rag"

    redis_url: str = "redis://localhost:6379/0"

    # Storage + AWS. Empty S3_ENDPOINT_URL -> real AWS S3; a URL -> MinIO.
    # S3_REGION is also the region for Textract.
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "ocr-rag-documents"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin"

    # LLM used for classification and structured extraction.
    openai_api_key: str = ""
    classifier_model: str = "gpt-4o-mini"
    extractor_model: str = "gpt-4o-mini"

    # Extracted fields below this confidence are flagged for human review.
    confidence_threshold: float = 0.7

    # RAG: chunking, embeddings, retrieval, answering.
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536
    answer_model: str = "gpt-4o-mini"
    retrieval_k: int = 8
    # Chunks past this cosine distance from the question are dropped, so an
    # off-topic query returns no sources instead of citing random text. Tuned
    # against text-embedding-3-small: real clause questions land ~0.55-0.78,
    # unrelated ("capital of France") ~0.95+.
    retrieval_max_distance: float = 0.85

    max_upload_bytes: int = 25 * 1024 * 1024

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


settings = Settings()
