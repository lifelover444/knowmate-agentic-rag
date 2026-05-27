from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import SecretCipher
from app.db.models import ModelConfig
from app.db.repositories.model_config import ModelConfigRepository
from app.integrations.llm_openai import OpenAICompatibleConfig
from app.schemas.model_config import ModelConfigPayload, ModelConfigRead
from app.schemas.models import (
    MODEL_TYPES,
    ModelCreate,
    ModelCredentialPayload,
    ModelCredentialsRead,
    ModelRead,
    ModelTestPayload,
    ModelUpdate,
)

MODEL_CONFIG_REQUIRED_MESSAGE = "请先配置并测试模型"
MODEL_NOT_AVAILABLE_MESSAGE = "模型不存在或不可用"


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

    def list_models(self, model_type: str | None = None) -> list[ModelRead]:
        return [self.to_model_read(item) for item in self.repo.list(self.settings.default_tenant_id, model_type)]

    def get_model_read(self, model_id: str) -> ModelRead:
        model = self._get_model(model_id)
        return self.to_model_read(model)

    def create_model(self, payload: ModelCreate) -> ModelRead:
        api_key = (payload.api_key or "").strip()
        if not api_key:
            raise ValueError("创建模型必须提供 API Key")
        config = ModelConfig(
            tenant_id=self.settings.default_tenant_id,
            type=payload.type,
            source=payload.source,
            provider=payload.provider,
            name=payload.name,
            base_url=payload.base_url,
            api_key_encrypted=SecretCipher(self.settings.model_config_encryption_key).encrypt(api_key),
            api_key_last4=api_key[-4:],
            chat_model=payload.model_name if payload.type != "Embedding" else "",
            embedding_model=payload.model_name if payload.type == "Embedding" else "",
            embedding_dimension=payload.embedding_dimension or 0,
            is_active=True,
            is_builtin=False,
            status="active",
        )
        self.repo.save(config)
        return self.to_model_read(config)

    def update_model(self, model_id: str, payload: ModelUpdate) -> ModelRead:
        model = self._get_model(model_id)
        if model.is_builtin:
            raise ValueError("内置模型不能编辑")
        if payload.name is not None:
            model.name = payload.name
        if payload.provider is not None:
            model.provider = payload.provider
        if payload.source is not None:
            model.source = payload.source
        if payload.base_url is not None:
            model.base_url = payload.base_url
        if payload.model_name is not None:
            if model.type == "Embedding":
                model.embedding_model = payload.model_name
            else:
                model.chat_model = payload.model_name
        if payload.embedding_dimension is not None:
            model.embedding_dimension = payload.embedding_dimension
        if payload.status is not None:
            model.status = payload.status
        self.repo.save(model)
        return self.to_model_read(model)

    def delete_model(self, model_id: str) -> None:
        model = self._get_model(model_id)
        if model.is_builtin:
            raise ValueError("内置模型不能删除")
        self.repo.delete(model)

    def update_credentials(self, model_id: str, payload: ModelCredentialPayload) -> ModelCredentialsRead:
        model = self._get_model(model_id)
        api_key = (payload.api_key or "").strip()
        if api_key:
            model.api_key_encrypted = SecretCipher(self.settings.model_config_encryption_key).encrypt(api_key)
            model.api_key_last4 = api_key[-4:]
            self.repo.save(model)
        return self.credentials_read(model)

    def clear_credential(self, model_id: str, field: str) -> None:
        if field != "api_key":
            raise ValueError("未知凭据字段")
        model = self._get_model(model_id)
        model.api_key_encrypted = ""
        model.api_key_last4 = ""
        self.repo.save(model)

    def test_model(self, payload: ModelTestPayload) -> dict:
        return self._test_runtime_config(self._runtime_config_from_model_test_payload(payload), model_type=payload.type)

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
                type="KnowledgeQA",
                source="remote",
                provider=payload.provider,
                name=payload.name or self._default_name(payload.provider),
                base_url=payload.base_url,
                api_key_encrypted=encrypted,
                api_key_last4=last4,
                chat_model=payload.chat_model,
                embedding_model=payload.embedding_model,
                embedding_dimension=payload.embedding_dimension,
                is_active=True,
                is_builtin=False,
                status="active",
            )
        else:
            config = existing
            config.type = config.type or "KnowledgeQA"
            config.source = config.source or "remote"
            config.provider = payload.provider
            config.name = payload.name or existing.name or self._default_name(payload.provider)
            config.base_url = payload.base_url
            config.api_key_encrypted = encrypted
            config.api_key_last4 = last4
            config.chat_model = payload.chat_model
            config.embedding_model = payload.embedding_model
            config.embedding_dimension = payload.embedding_dimension
            config.is_active = True
            config.status = "active"
        self.repo.save(config)
        return self.to_read(config)

    def test(self, payload: ModelConfigPayload | None) -> dict:
        runtime_config = self.build_runtime_config(payload)
        return self._test_runtime_config(runtime_config)

    def _test_runtime_config(self, runtime_config: OpenAICompatibleConfig, model_type: str | None = None) -> dict:
        if self.tester is None:
            from app.integrations.llm_openai import OpenAICompatibleModelTester

            self.tester = OpenAICompatibleModelTester()
        if model_type == "KnowledgeQA" and hasattr(self.tester, "test_chat"):
            return self.tester.test_chat(runtime_config)
        if model_type == "Embedding" and hasattr(self.tester, "test_embedding"):
            return self.tester.test_embedding(runtime_config)
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

    def build_runtime_config_for_model(self, model_id: str, expected_type: str) -> OpenAICompatibleConfig:
        model = self._get_model(model_id)
        if model.type != expected_type or model.status != "active":
            raise RuntimeError(MODEL_NOT_AVAILABLE_MESSAGE)
        return self._runtime_config_from_model(model)

    def get_model(self, model_id: str, expected_type: str | None = None) -> ModelConfig:
        model = self._get_model(model_id)
        if expected_type and model.type != expected_type:
            raise RuntimeError(MODEL_NOT_AVAILABLE_MESSAGE)
        if model.status != "active":
            raise RuntimeError(MODEL_NOT_AVAILABLE_MESSAGE)
        return model

    def decrypt_api_key(self, config: ModelConfig) -> str:
        if not config.api_key_encrypted:
            raise RuntimeError("模型 API Key 未配置")
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

    def to_model_read(self, config: ModelConfig) -> ModelRead:
        return ModelRead(
            id=config.id,
            tenant_id=config.tenant_id,
            name=config.name,
            type=config.type,
            provider=config.provider,
            source=config.source,
            base_url=config.base_url,
            model_name=self._model_name(config),
            embedding_dimension=config.embedding_dimension if config.type == "Embedding" else None,
            status=config.status,
            is_builtin=config.is_builtin,
            api_key_configured=bool(config.api_key_encrypted),
            api_key_last4=config.api_key_last4 or None,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def credentials_read(self, config: ModelConfig) -> ModelCredentialsRead:
        return ModelCredentialsRead(fields={"api_key": {"configured": bool(config.api_key_encrypted)}})

    def _default_name(self, provider: str) -> str:
        if provider == "qwen":
            return "Qwen / DashScope"
        return "OpenAI Compatible"

    def _get_model(self, model_id: str) -> ModelConfig:
        model = self.repo.get(self.settings.default_tenant_id, model_id)
        if model is None:
            raise LookupError(MODEL_NOT_AVAILABLE_MESSAGE)
        return model

    def _model_name(self, config: ModelConfig) -> str:
        return config.embedding_model if config.type == "Embedding" else config.chat_model

    def _runtime_config_from_model(self, config: ModelConfig) -> OpenAICompatibleConfig:
        model_name = self._model_name(config)
        return OpenAICompatibleConfig(
            provider=config.provider,
            base_url=config.base_url,
            api_key=self.decrypt_api_key(config),
            chat_model=model_name if config.type != "Embedding" else "",
            embedding_model=model_name if config.type == "Embedding" else "",
            embedding_dimension=config.embedding_dimension,
        )

    def _runtime_config_from_model_payload(
        self,
        payload: ModelCreate,
        api_key: str | None = None,
    ) -> OpenAICompatibleConfig:
        if payload.type not in MODEL_TYPES:
            raise ValueError("不支持的模型类型")
        resolved_api_key = api_key if api_key is not None else payload.api_key
        return OpenAICompatibleConfig(
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=(resolved_api_key or "").strip(),
            chat_model=payload.model_name if payload.type != "Embedding" else payload.model_name,
            embedding_model=payload.model_name,
            embedding_dimension=payload.embedding_dimension or self.settings.embedding_dimension,
        )

    def _runtime_config_from_model_test_payload(self, payload: ModelTestPayload) -> OpenAICompatibleConfig:
        api_key = (payload.api_key or "").strip()
        if api_key:
            return self._runtime_config_from_model_payload(payload, api_key)

        if not payload.model_id:
            raise ValueError("请填写 API Key，或先选择一个已保存的模型后再测试")

        model = self._get_model(payload.model_id)
        if model.type != payload.type:
            raise ValueError("选择的模型类型与测试类型不匹配")
        if model.status != "active":
            raise ValueError("模型已停用，无法测试")
        return self._runtime_config_from_model_payload(payload, self.decrypt_api_key(model))
