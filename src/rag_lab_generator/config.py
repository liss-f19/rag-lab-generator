"""Application settings, read from environment variables or a .env file (NFR-20)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/rag_lab"
    redis_url: str = "redis://localhost:6379/0"
    queue_backend: Literal["rq", "inline"] = "rq"
    queue_name: str = "rag-lab"
    job_timeout_seconds: int = Field(default=1800, gt=0)

    file_storage_dir: Path = Path("./data/files")
    chroma_persist_directory: Path = Path("./data/chroma")

    embedding_provider: Literal["openai", "hashing"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    hashing_dimensions: int = Field(default=1024, ge=64)
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    openai_timeout_seconds: float = Field(default=30.0, gt=0)
    openai_max_retries: int = Field(default=3, ge=0)

    token_signing_key: SecretStr = Field(min_length=32)
    token_ttl_minutes: int = Field(default=12 * 60, gt=0)

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    chunk_max_chars: int = Field(default=1200, ge=100)
    chunk_overlap_chars: int = Field(default=150, ge=0)
    retrieval_default_top_k: int = Field(default=5, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
