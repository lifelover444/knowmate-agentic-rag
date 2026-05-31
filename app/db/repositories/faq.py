from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FAQEntry


class FAQEntryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, entry: FAQEntry) -> FAQEntry:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get(self, entry_id: str, tenant_id: int | None = None) -> FAQEntry | None:
        query = select(FAQEntry).where(FAQEntry.id == entry_id, FAQEntry.deleted_at.is_(None))
        if tenant_id is not None:
            query = query.where(FAQEntry.tenant_id == tenant_id)
        return self.db.scalar(query)

    def list_by_knowledge_base(self, kb_id: str, *, tag_id: str | None = None) -> list[FAQEntry]:
        query = select(FAQEntry).where(FAQEntry.knowledge_base_id == kb_id, FAQEntry.deleted_at.is_(None))
        if tag_id:
            query = query.where(FAQEntry.tag_id == tag_id)
        return list(
            self.db.scalars(
                query.order_by(FAQEntry.created_at.desc(), FAQEntry.id.desc())
            ).all()
        )

    def save(self, entry: FAQEntry) -> FAQEntry:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def soft_delete(self, entry: FAQEntry) -> FAQEntry:
        entry.deleted_at = datetime.now(UTC)
        entry.enabled = False
        return self.save(entry)
