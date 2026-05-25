from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import SecretCipher
from app.db.models import ModelConfig
from app.db.repositories.model_config import ModelConfigRepository
from app.integrations.llm_openai import OpenAICompatibleConfig
from app.schemas.model_config import ModelConfigPayload, ModelConfigRead

MODEL_CONFIG_REQUIRED_MESSAGE = "请先配置并测试模型"


@dataclass(frozen=True)
class RuntimeModelClients:
    config: OpenAICompatibleConfig
    embedder: object
    chat_model: object


class ModelConfigService:
    def __init__(self, db: Session, settings: Settings, tester=None) -> None:
        self.db = db
        self.settings = settings
        self.repo = ModelConfigRepository(db)
        self.tester = tester

    def get_active(self) -> ModelConfig | None:
        return self.repo.get_active(self.settings.default_tenant_id)

    def read_active(self) -> ModelConfigRead | None:
        config = self.get_active()
        return self.to_read(config) if config else None

    def save(self, payload: ModelConfigPayload) -> ModelConfigRead:
        existing = self.get_active()
        api_key = payload.api_key.strip() if payload.api_key else None
        if existing is None and not api_key:
            raise ValueError("首次保存模型配置必须提供 API Key")

        cipher = SecretCipher(self.settings.model_config_encryption_key)
        encrypted = existing.api_key_encrypted if existing else ""
        last4 = existing.api_key_last4 if existing else ""
        if api_key:
            encrypted = cipher.encrypt(api_key)
            last4 = api_key[-4:]

        if existing is None:
            config = ModelConfig(
                tenant_id=self.settings.default_tenant_id,
                provider=payload.provider,
                name=payload.name or self._default_name(payload.provider),
                base_url=payload.base_url,
                api_key_encrypted=encrypted,
                api_key_last4=last4,
                chat_model=payload.chat_model,
                embedding_model=payload.embedding_model,
                embedding_dimension=payload.embedding_dimension,
                is_active=True,
            )
        else:
            config = existing
            config.provider = payload.provider
            config.name = payload.name or existing.name or self._default_name(payload.provider)
            config.base_url = payload.base_url
            config.api_key_encrypted = encrypted
            config.api_key_last4 = last4
            config.chat_model = payload.chat_model
            config.embedding_model = payload.embedding_model
            config.embedding_dimension = payload.embedding_dimension
            config.is_active = True
        self.repo.save(config)
        return self.to_read(config)

    def test(self, payload: ModelConfigPayload | None) -> dict:
        runtime_config = self.build_runtime_config(payload)
        if self.tester is None:
            from app.integrations.llm_openai import OpenAICompatibleModelTester

            self.tester = OpenAICompatibleModelTester()
        return self.tester.test(runtime_config)

    def build_runtime_config(self, payload: ModelConfigPayload | None = None) -> OpenAICompatibleConfig:
        if payload is not None:
            api_key = payload.api_key.strip() if payload.api_key else None
            if not api_key:
                active = self.get_active()
                if active is None:
                    raise RuntimeError(MODEL_CONFIG_REQUIRED_MESSAGE)
                api_key = self.decrypt_api_key(active)
            return OpenAICompatibleConfig(
                provider=payload.provider,
                base_url=payload.base_url,
                api_key=api_key,
                chat_model=payload.chat_model,
                embedding_model=payload.embedding_model,
                embedding_dimension=payload.embedding_dimension,
            )

        active = self.get_active()
        if active is None:
            raise RuntimeError(MODEL_CONFIG_REQUIRED_MESSAGE)
        return OpenAICompatibleConfig(
            provider=active.provider,
            base_url=active.base_url,
            api_key=self.decrypt_api_key(active),
            chat_model=active.chat_model,
            embedding_model=active.embedding_model,
            embedding_dimension=active.embedding_dimension,
        )

    def decrypt_api_key(self, config: ModelConfig) -> str:
        return SecretCipher(self.settings.model_config_encryption_key).decrypt(config.api_key_encrypted)

    def to_read(self, config: ModelConfig) -> ModelConfigRead:
        return ModelConfigRead(
            id=config.id,
            tenant_id=config.tenant_id,
            provider=config.provider,
            name=config.name,
            base_url=config.base_url,
            chat_model=config.chat_model,
            embedding_model=config.embedding_model,
            embedding_dimension=config.embedding_dimension,
            is_active=config.is_active,
            api_key_configured=bool(config.api_key_encrypted),
            api_key_last4=config.api_key_last4 or None,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def _default_name(self, provider: str) -> str:
        if provider == "qwen":
            return "Qwen / DashScope"
        return "OpenAI Compatible"
