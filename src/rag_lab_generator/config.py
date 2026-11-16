"""
Role:   Single source of runtime configuration for every layer.
Input:  Environment variables and an optional .env file in the working directory.
Output: Settings instance via get_settings(); cached for the process lifetime.
Flow:   pydantic-settings reads env vars (case-insensitive), validates types, resolves
        data_dir to an absolute path; get_settings() memoizes one instance.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # llm
    anthropic_api_key: SecretStr | None = None
    llm_provider: str = "fake"
    llm_model: str = "claude-opus-5"
    llm_max_tokens: int = 16000

    # embeddings
    embedding_provider: str = "bge_m3"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_batch_size: int = 16
    hf_api_token: SecretStr | None = None

    # storage
    database_url: str = "postgresql://rag:rag@localhost:5433/raglab"
    data_dir: Path = Path("data")
    results_dir: Path = Path("results")

    # corpus sources
    sop_site_repo_url: str = "https://github.com/SOP-MINI/sop-site.git"
    sop_site_base_url: str = "https://sop.mini.pw.edu.pl"
    kozlowski_base_url: str = "https://pages.mini.pw.edu.pl/~kozlowskim"
    corpus_lang: str = "en"

    # default strategies (each must be a registered name)
    chunker: str = "hierarchical"
    searcher: str = "hybrid_rrf_idf"
    rag: str = "vector"
    chunk_size: int = Field(default=1000, description="target chunk size in characters")
    chunk_overlap_ratio: float = 0.1
    retrieval_k: int = 8
    rrf_k: int = 60
    graph_hops: int = 1

    log_level: str = "INFO"

    @field_validator("data_dir", "results_dir")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def external_dir(self) -> Path:
        return self.data_dir / "external"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
