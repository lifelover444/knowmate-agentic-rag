from app.core.config import Settings
from app.integrations.opensearch_store import OpenSearchSparseStore
from app.integrations.qdrant_store import QdrantVectorStore

SENSITIVE_CONFIG_KEYS = {"api_key", "password", "secret", "token"}


def mask_vector_store_config(config: dict | None) -> dict:
    masked: dict = {}
    for key, value in (config or {}).items():
        if key.lower() in SENSITIVE_CONFIG_KEYS:
            masked[f"{key}_configured"] = bool(value)
            if value:
                masked[f"{key}_last4"] = str(value)[-4:]
            continue
        masked[key] = value
    return masked


class VectorStoreRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, provider: str, config: dict | None = None):
        provider = provider.lower()
        config = config or {}
        if provider == "qdrant":
            return QdrantVectorStore(self.settings, config=config)
        if provider in {"opensearch", "elasticsearch"}:
            if config.get("fake") or config.get("client"):
                return OpenSearchSparseStore(config=config)
            raise ValueError("OpenSearch/Elasticsearch VectorStore 未配置，当前 Quick Q&A 默认仅启用 Qdrant")
        raise ValueError(f"不支持的 VectorStore provider：{provider}")

    def default_config(self) -> dict:
        return {
            "host": self.settings.qdrant_host,
            "port": self.settings.qdrant_port,
            "api_key": self.settings.qdrant_api_key,
            "use_tls": self.settings.qdrant_use_tls,
            "collection": self.settings.qdrant_collection,
        }
