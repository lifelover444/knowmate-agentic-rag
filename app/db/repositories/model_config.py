from sqlalchemy.orm import Session

from app.db.models import ModelConfig


class ModelConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, tenant_id: int) -> ModelConfig | None:
        return (
            self.db.query(ModelConfig)
            .filter(ModelConfig.tenant_id == tenant_id, ModelConfig.is_active.is_(True))
            .filter(ModelConfig.type.in_(["KnowledgeQA", "legacy"]))
            .order_by(ModelConfig.updated_at.desc())
            .first()
        )

    def get(self, tenant_id: int, model_id: str) -> ModelConfig | None:
        return (
            self.db.query(ModelConfig)
            .filter(ModelConfig.tenant_id == tenant_id, ModelConfig.id == model_id)
            .first()
        )

    def list(self, tenant_id: int, model_type: str | None = None) -> list[ModelConfig]:
        query = self.db.query(ModelConfig).filter(ModelConfig.tenant_id == tenant_id)
        if model_type:
            query = query.filter(ModelConfig.type == model_type)
        return query.order_by(ModelConfig.type.asc(), ModelConfig.updated_at.desc()).all()

    def get_first_by_type(self, tenant_id: int, model_type: str) -> ModelConfig | None:
        return (
            self.db.query(ModelConfig)
            .filter(
                ModelConfig.tenant_id == tenant_id,
                ModelConfig.type == model_type,
                ModelConfig.status == "active",
            )
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

    def delete(self, config: ModelConfig) -> None:
        self.db.delete(config)
        self.db.commit()
