from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ParserProviderConfig


class ParserProviderConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_provider(self, tenant_id: int, provider: str) -> ParserProviderConfig | None:
        return self.db.scalar(
            select(ParserProviderConfig).where(
                ParserProviderConfig.tenant_id == tenant_id,
                ParserProviderConfig.provider == provider,
            )
        )

    def list(self, tenant_id: int) -> list[ParserProviderConfig]:
        return list(
            self.db.scalars(
                select(ParserProviderConfig)
                .where(ParserProviderConfig.tenant_id == tenant_id)
                .order_by(ParserProviderConfig.provider.asc(), ParserProviderConfig.updated_at.desc())
            ).all()
        )

    def save(self, config: ParserProviderConfig) -> ParserProviderConfig:
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config
