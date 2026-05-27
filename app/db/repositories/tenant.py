from sqlalchemy.orm import Session

from app.db.models import Tenant


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, tenant_id: int) -> Tenant:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            tenant = Tenant(id=tenant_id, name="default", description="knowmate default tenant")
            self.db.add(tenant)
            self.db.commit()
            self.db.refresh(tenant)
        return tenant

    def save(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant
