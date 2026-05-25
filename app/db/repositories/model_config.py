from sqlalchemy.orm import Session

from app.db.models import ModelConfig


class ModelConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, tenant_id: int) -> ModelConfig | None:
        return (
            self.db.query(ModelConfig)
            .filter(ModelConfig.tenant_id == tenant_id, ModelConfig.is_active.is_(True))
            .order_by(ModelConfig.updated_at.desc())
            .first()
        )

    def deactivate_all(self, tenant_id: int) -> None:
        self.db.query(ModelConfig).filter(ModelConfig.tenant_id == tenant_id).update({"is_active": False})

    def save(self, config: ModelConfig) -> ModelConfig:
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config
