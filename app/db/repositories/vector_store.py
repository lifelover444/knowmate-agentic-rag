from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import VectorStoreConfig


class VectorStoreRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, store: VectorStoreConfig) -> VectorStoreConfig:
        if store.is_default:
            self.clear_default(store.tenant_id)
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)
        return store

    def get(self, store_id: str, tenant_id: int | None = None) -> VectorStoreConfig | None:
        query = select(VectorStoreConfig).where(VectorStoreConfig.id == store_id)
        if tenant_id is not None:
            query = query.where(VectorStoreConfig.tenant_id == tenant_id)
        return self.db.scalar(query)

    def list(self, tenant_id: int) -> list[VectorStoreConfig]:
        return list(
            self.db.scalars(
                select(VectorStoreConfig)
                .where(VectorStoreConfig.tenant_id == tenant_id)
                .order_by(VectorStoreConfig.is_default.desc(), VectorStoreConfig.created_at.desc())
            ).all()
        )

    def default(self, tenant_id: int) -> VectorStoreConfig | None:
        return self.db.scalar(
            select(VectorStoreConfig).where(
                VectorStoreConfig.tenant_id == tenant_id,
                VectorStoreConfig.is_default.is_(True),
            )
        )

    def save(self, store: VectorStoreConfig) -> VectorStoreConfig:
        if store.is_default:
            self.clear_default(store.tenant_id, except_id=store.id)
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)
        return store

    def delete(self, store: VectorStoreConfig) -> None:
        self.db.delete(store)
        self.db.commit()

    def clear_default(self, tenant_id: int, except_id: str | None = None) -> None:
        stores = self.list(tenant_id)
        for store in stores:
            if except_id is not None and store.id == except_id:
                continue
            store.is_default = False
            self.db.add(store)
        self.db.flush()
