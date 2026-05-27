from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.tenant import TenantRepository
from app.schemas.retrieval import RetrievalConfigSchema, default_retrieval_config


class RetrievalConfigService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.repo = TenantRepository(db)
        self.settings = settings

    def get(self) -> RetrievalConfigSchema:
        tenant = self.repo.get_or_create(self.settings.default_tenant_id)
        return RetrievalConfigSchema(**{**default_retrieval_config(), **(tenant.retrieval_config or {})})

    def save(self, payload: RetrievalConfigSchema) -> RetrievalConfigSchema:
        tenant = self.repo.get_or_create(self.settings.default_tenant_id)
        tenant.retrieval_config = payload.model_dump()
        self.repo.save(tenant)
        return self.get()
