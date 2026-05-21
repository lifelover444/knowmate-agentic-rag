from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "knowmate知友"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    default_tenant_id: int = 10000

    database_url: str = "postgresql+psycopg://knowmate:knowmate@localhost:15432/knowmate"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    upload_dir: Path = Path("./storage/uploads")

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_use_tls: bool = False
    qdrant_collection: str = "knowmate_embeddings"

    openai_api_key: str = Field(default="change-me")
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    default_chunk_size: int = 512
    default_chunk_overlap: int = 80
    quick_answer_top_k: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
