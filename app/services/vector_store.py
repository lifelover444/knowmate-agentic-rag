from app.core.config import Settings
from app.db.models import VectorStoreConfig
from app.db.repositories.vector_store import VectorStoreRepository
from app.integrations.vector_store import VectorStoreRegistry, mask_vector_store_config
from app.schemas.vector_store import VectorStoreCreate, VectorStoreUpdate


class VectorStoreService:
    def __init__(self, repo: VectorStoreRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.registry = VectorStoreRegistry(settings)

    def create(self, payload: VectorStoreCreate) -> VectorStoreConfig:
        self._validate_provider(payload.provider)
        return self.repo.create(
            VectorStoreConfig(
                tenant_id=self.settings.default_tenant_id,
                name=payload.name,
                provider=payload.provider.lower(),
                config_json=payload.config_json,
                status=payload.status,
                is_default=payload.is_default,
            )
        )

    def update(self, store: VectorStoreConfig, payload: VectorStoreUpdate) -> VectorStoreConfig:
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            store.name = data["name"]
        if "provider" in data and data["provider"] is not None:
            self._validate_provider(data["provider"])
            store.provider = data["provider"].lower()
        if "config_json" in data and data["config_json"] is not None:
            store.config_json = {**(store.config_json or {}), **data["config_json"]}
        if "status" in data and data["status"] is not None:
            store.status = data["status"]
        if "is_default" in data and data["is_default"] is not None:
            store.is_default = data["is_default"]
        return self.repo.save(store)

    def delete(self, store: VectorStoreConfig) -> None:
        if store.is_default:
            raise ValueError("默认 VectorStore 不能删除")
        self.repo.delete(store)

    def test_connection(self, provider: str, config: dict, *, dry_run: bool = False) -> tuple[bool, str]:
        self._validate_provider(provider)
        if dry_run:
            return True, "Qdrant VectorStore 配置格式有效"
        try:
            self.registry.build(provider, config).test_connection()
        except Exception as exc:
            return False, f"Qdrant 连接失败：{exc}"
        return True, "Qdrant 连接测试通过"

    def ensure_default(self) -> VectorStoreConfig:
        existing = self.repo.default(self.settings.default_tenant_id)
        if existing is not None:
            return existing
        return self.repo.create(
            VectorStoreConfig(
                tenant_id=self.settings.default_tenant_id,
                name="默认 Qdrant",
                provider="qdrant",
                config_json=self.registry.default_config(),
                status="active",
                is_default=True,
            )
        )

    def _validate_provider(self, provider: str) -> None:
        if provider.lower() != "qdrant":
            raise ValueError("v0.5 仅支持 Qdrant VectorStore")


def to_safe_vector_store(store: VectorStoreConfig) -> dict:
    return {
        **store.__dict__,
        "config_json": mask_vector_store_config(store.config_json),
    }
