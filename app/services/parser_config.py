from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import SecretCipher
from app.db.models import ParserProviderConfig
from app.db.repositories.parser_provider_config import ParserProviderConfigRepository
from app.schemas.parser_config import ParserConfigPayload, ParserConfigRead, ParserCredentialsRead

MINERU_PROVIDER = "mineru"
MINERU_CONFIG_REQUIRED_MESSAGE = "请先在解析器设置中配置 MinerU API Key"


def default_mineru_config() -> dict[str, Any]:
    return {
        "model_version": "vlm",
        "language": "ch",
        "enable_table": True,
        "enable_formula": True,
        "is_ocr": False,
        "poll_interval_seconds": 3,
        "poll_timeout_seconds": 600,
    }


@dataclass(frozen=True)
class RuntimeParserConfig:
    provider: str
    base_url: str
    api_key: str
    config: dict[str, Any]


class ParserProviderConfigService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = ParserProviderConfigRepository(db)

    def get_read(self, provider: str = MINERU_PROVIDER) -> ParserConfigRead:
        config = self.repo.get_by_provider(self.settings.default_tenant_id, provider)
        if config is None:
            return self._missing_read(provider)
        return self.to_read(config)

    def list_configs(self) -> list[ParserConfigRead]:
        configs = self.repo.list(self.settings.default_tenant_id)
        if not configs:
            return [self._missing_read(MINERU_PROVIDER)]
        return [self.to_read(config) for config in configs]

    def save(self, provider: str, payload: ParserConfigPayload) -> ParserConfigRead:
        normalized_provider = _normalize_provider(provider)
        existing = self.repo.get_by_provider(self.settings.default_tenant_id, normalized_provider)
        api_key = (payload.api_key or "").strip()
        if existing is None and not api_key:
            raise ValueError("首次保存 MinerU 配置必须提供 API Key")

        encrypted = existing.api_key_encrypted if existing else ""
        last4 = existing.api_key_last4 if existing else ""
        if api_key:
            encrypted = SecretCipher(self.settings.model_config_encryption_key).encrypt(api_key)
            last4 = api_key[-4:]

        config_json = default_mineru_config()
        config_json.update(payload.config or {})
        if existing is None:
            config = ParserProviderConfig(
                tenant_id=self.settings.default_tenant_id,
                provider=normalized_provider,
                name=payload.name,
                base_url=payload.base_url.rstrip("/"),
                status=payload.status or "active",
                config_json=config_json,
                api_key_encrypted=encrypted,
                api_key_last4=last4,
            )
        else:
            config = existing
            config.name = payload.name
            config.base_url = payload.base_url.rstrip("/")
            config.status = payload.status or "active"
            config.config_json = config_json
            config.api_key_encrypted = encrypted
            config.api_key_last4 = last4
        return self.to_read(self.repo.save(config))

    def update_credentials(self, provider: str, api_key: str | None) -> ParserCredentialsRead:
        config = self._get_existing(provider)
        normalized = (api_key or "").strip()
        if normalized:
            config.api_key_encrypted = SecretCipher(self.settings.model_config_encryption_key).encrypt(normalized)
            config.api_key_last4 = normalized[-4:]
            self.repo.save(config)
        return self.credentials_read(config)

    def clear_credential(self, provider: str, field: str) -> None:
        if field != "api_key":
            raise ValueError("未知凭据字段")
        config = self._get_existing(provider)
        config.api_key_encrypted = ""
        config.api_key_last4 = ""
        self.repo.save(config)

    def runtime_config(self, provider: str = MINERU_PROVIDER) -> RuntimeParserConfig:
        config = self._get_existing(provider)
        if config.status != "active":
            raise RuntimeError("MinerU 解析器未启用")
        if not config.api_key_encrypted:
            raise RuntimeError(MINERU_CONFIG_REQUIRED_MESSAGE)
        return RuntimeParserConfig(
            provider=config.provider,
            base_url=config.base_url,
            api_key=SecretCipher(self.settings.model_config_encryption_key).decrypt(config.api_key_encrypted),
            config={**default_mineru_config(), **(config.config_json or {})},
        )

    def to_read(self, config: ParserProviderConfig) -> ParserConfigRead:
        return ParserConfigRead(
            id=config.id,
            tenant_id=config.tenant_id,
            provider=config.provider,
            name=config.name,
            base_url=config.base_url,
            status=config.status,
            config={**default_mineru_config(), **(config.config_json or {})},
            api_key_configured=bool(config.api_key_encrypted),
            api_key_last4=config.api_key_last4 or None,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def credentials_read(self, config: ParserProviderConfig) -> ParserCredentialsRead:
        return ParserCredentialsRead(fields={"api_key": {"configured": bool(config.api_key_encrypted)}})

    def _missing_read(self, provider: str) -> ParserConfigRead:
        return ParserConfigRead(
            tenant_id=self.settings.default_tenant_id,
            provider=_normalize_provider(provider),
            name="MinerU",
            base_url="https://mineru.net/api/v4",
            status="missing",
            config=default_mineru_config(),
            api_key_configured=False,
        )

    def _get_existing(self, provider: str) -> ParserProviderConfig:
        config = self.repo.get_by_provider(self.settings.default_tenant_id, _normalize_provider(provider))
        if config is None:
            raise LookupError("解析器配置不存在")
        return config


def _normalize_provider(provider: str) -> str:
    normalized = (provider or MINERU_PROVIDER).strip().lower()
    if normalized != MINERU_PROVIDER:
        raise ValueError("当前仅支持 MinerU 解析器配置")
    return normalized
