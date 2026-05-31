from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, session: ChatSession) -> ChatSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, tenant_id: int) -> list[ChatSession]:
        return list(
            self.db.scalars(
                select(ChatSession)
                .where(ChatSession.tenant_id == tenant_id, ChatSession.deleted_at.is_(None))
                .order_by(
                    ChatSession.is_pinned.desc(),
                    ChatSession.last_message_at.desc(),
                    ChatSession.created_at.desc(),
                )
            ).all()
        )

    def get_session(self, session_id: str, tenant_id: int) -> ChatSession | None:
        return self.db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.tenant_id == tenant_id,
                ChatSession.deleted_at.is_(None),
            )
        )

    def save_session(self, session: ChatSession) -> ChatSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def soft_delete_session(self, session: ChatSession) -> None:
        session.deleted_at = datetime.now(UTC)
        self.db.add(session)
        self.db.commit()

    def list_messages(self, session_id: str, tenant_id: int) -> list[ChatMessage]:
        return list(
            self.db.scalars(
                select(ChatMessage)
                .where(ChatMessage.tenant_id == tenant_id, ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            ).all()
        )

    def create_message(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
