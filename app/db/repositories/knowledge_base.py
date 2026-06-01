from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Knowledge, KnowledgeBase, KnowledgeBasePin


class KnowledgeBaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, kb: KnowledgeBase) -> KnowledgeBase:
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def list(self, tenant_id: int) -> list[KnowledgeBase]:
        items = list(
            self.db.scalars(
                select(KnowledgeBase)
                .where(KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.deleted_at.is_(None))
                .order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc())
            ).all()
        )
        pin_map = self.list_pin_map(tenant_id)
        return sorted(items, key=lambda kb: _pin_sort_key(kb, pin_map))

    def get(self, kb_id: str, tenant_id: int) -> KnowledgeBase | None:
        return self.db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.deleted_at.is_(None),
            )
        )

    def counts(self, kb_id: str) -> tuple[int, int, int]:
        document_count = (
            self.db.scalar(
                select(func.count(Knowledge.id)).where(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.deleted_at.is_(None),
                )
            )
            or 0
        )
        chunk_count = (
            self.db.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.knowledge_base_id == kb_id,
                    Chunk.deleted_at.is_(None),
                )
            )
            or 0
        )
        processing_count = (
            self.db.scalar(
                select(func.count(Knowledge.id)).where(
                    Knowledge.knowledge_base_id == kb_id,
                    Knowledge.deleted_at.is_(None),
                    Knowledge.parse_status.in_(("pending", "processing")),
                )
            )
            or 0
        )
        return int(document_count), int(chunk_count), int(processing_count)

    def save(self, kb: KnowledgeBase) -> KnowledgeBase:
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def soft_delete(self, kb: KnowledgeBase) -> KnowledgeBase:
        kb.deleted_at = datetime.now(UTC)
        self.db.execute(delete(KnowledgeBasePin).where(KnowledgeBasePin.knowledge_base_id == kb.id))
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def list_pin_map(self, tenant_id: int) -> dict[str, datetime]:
        rows = self.db.execute(
            select(KnowledgeBasePin.knowledge_base_id, KnowledgeBasePin.pinned_at).where(
                KnowledgeBasePin.tenant_id == tenant_id
            )
        ).all()
        return {str(kb_id): pinned_at for kb_id, pinned_at in rows}

    def pinned_at(self, kb_id: str, tenant_id: int) -> datetime | None:
        return self.db.scalar(
            select(KnowledgeBasePin.pinned_at).where(
                KnowledgeBasePin.knowledge_base_id == kb_id,
                KnowledgeBasePin.tenant_id == tenant_id,
            )
        )

    def set_pin(self, kb_id: str, tenant_id: int, pinned: bool) -> datetime | None:
        existing = self.db.scalar(
            select(KnowledgeBasePin).where(
                KnowledgeBasePin.knowledge_base_id == kb_id,
                KnowledgeBasePin.tenant_id == tenant_id,
            )
        )
        if not pinned:
            if existing is not None:
                self.db.delete(existing)
                self.db.commit()
            return None

        now = datetime.now(UTC)
        if existing is None:
            existing = KnowledgeBasePin(tenant_id=tenant_id, knowledge_base_id=kb_id, pinned_at=now)
        else:
            existing.pinned_at = now
        self.db.add(existing)
        self.db.commit()
        return now


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return 0
    return value.timestamp()


def _pin_sort_key(kb: KnowledgeBase, pin_map: dict[str, datetime]) -> tuple[int, float, float]:
    pinned_at = pin_map.get(kb.id)
    return (
        0 if pinned_at is not None else 1,
        -_timestamp(pinned_at),
        -_timestamp(kb.created_at),
    )
