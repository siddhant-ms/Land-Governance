"""Environment-driven configuration. No secrets are hard-coded for production."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_name: str = "SIH26019 Land Governance Evidence Platform"
    environment: str = "development"  # development | test | production
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'dev.sqlite3'}"
    redis_url: str = ""
    job_backend: str = "inline"  # inline | celery

    # auth
    jwt_secret: str = "dev-only-insecure-secret-change-me-32-bytes-min"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    # providers
    llm_provider: str = "extractive"  # extractive | anthropic | openai
    embedding_provider: str = "hashing"  # hashing | openai
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-5"

    # search (kept behind an abstraction)
    search_backend: str = "local"
    opensearch_url: str = ""
    opensearch_username: str = ""
    opensearch_password: str = ""

    # object storage (local filesystem implementation)
    object_storage_url: str = str(REPO_ROOT / "data" / "documents" / "_store")
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""

    # limits / security
    max_upload_bytes: int = 15 * 1024 * 1024
    rate_limit_enabled: bool = True
    cors_origins: str = "http://localhost:3000"

    # RAG thresholds
    rag_min_retrieval_score: float = 0.12  # top-1 relevance (0-1) below this => evidence gap
    rag_min_claim_support: float = 0.35  # fraction of claim content-tokens found in cited chunk
    rag_max_chunks_per_doc: int = 2
    rag_max_evidence: int = 8

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be set in production")
    return s
