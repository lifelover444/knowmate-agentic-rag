from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Knowledge


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: Knowledge) -> Knowledge:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get(self, document_id: str) -> Knowledge | None:
        return self.db.scalar(select(Knowledge).where(Knowledge.id == document_id, Knowledge.deleted_at.is_(None)))

    def save(self, document: Knowledge) -> Knowledge:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document
