from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, Chunk, FAQEntry, Knowledge


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, session: ChatSession) -> ChatSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, tenant_id: int, keyword: str | None = None) -> list[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.tenant_id == tenant_id, ChatSession.deleted_at.is_(None))
        if keyword:
            pattern = f"%{keyword.strip()}%"
            message_match = (
                select(ChatMessage.id)
                .where(
                    ChatMessage.tenant_id == tenant_id,
                    ChatMessage.session_id == ChatSession.id,
                    ChatMessage.content.ilike(pattern),
                )
                .exists()
            )
            stmt = stmt.where(or_(ChatSession.title.ilike(pattern), message_match))

        return list(
            self.db.scalars(
                stmt.order_by(
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

    def soft_delete_sessions(self, sessions: list[ChatSession]) -> None:
        now = datetime.now(UTC)
        for session in sessions:
            session.deleted_at = now
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

    def search_messages_by_keyword(
        self,
        tenant_id: int,
        keyword: str,
        session_ids: list[str] | None = None,
        limit: int = 20,
    ) -> list[tuple[ChatMessage, ChatSession]]:
        pattern = f"%{keyword.strip()}%"
        stmt = (
            select(ChatMessage, ChatSession)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.deleted_at.is_(None),
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.content.ilike(pattern),
            )
        )
        if session_ids:
            stmt = stmt.where(ChatMessage.session_id.in_(session_ids))
        ordered = stmt.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
        return list(self.db.execute(ordered).all())

    def chat_history_stats(self, tenant_id: int) -> tuple[int, int, datetime | None]:
        session_count = self.db.scalar(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.tenant_id == tenant_id, ChatSession.deleted_at.is_(None))
        )
        message_count = self.db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.deleted_at.is_(None),
                ChatMessage.tenant_id == tenant_id,
            )
        )
        last_message_at = self.db.scalar(
            select(func.max(ChatMessage.created_at))
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.deleted_at.is_(None),
                ChatMessage.tenant_id == tenant_id,
            )
        )
        return int(session_count or 0), int(message_count or 0), last_message_at

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

    def list_recommended_faqs(self, knowledge_base_id: str, tenant_id: int, limit: int) -> list[FAQEntry]:
        return list(
            self.db.scalars(
                select(FAQEntry)
                .where(
                    FAQEntry.tenant_id == tenant_id,
                    FAQEntry.knowledge_base_id == knowledge_base_id,
                    FAQEntry.enabled.is_(True),
                    FAQEntry.deleted_at.is_(None),
                )
                .order_by(FAQEntry.is_recommended.desc(), FAQEntry.updated_at.desc(), FAQEntry.created_at.desc())
                .limit(limit)
            ).all()
        )

    def list_recommended_chunks(
        self, knowledge_base_id: str, tenant_id: int, limit: int
    ) -> list[tuple[Chunk, Knowledge]]:
        return list(
            self.db.execute(
                select(Chunk, Knowledge)
                .join(Knowledge, Knowledge.id == Chunk.knowledge_id)
                .where(
                    Chunk.tenant_id == tenant_id,
                    Chunk.knowledge_base_id == knowledge_base_id,
                    Chunk.is_enabled.is_(True),
                    Chunk.deleted_at.is_(None),
                    Knowledge.deleted_at.is_(None),
                )
                .order_by(Chunk.created_at.desc(), Chunk.chunk_index.asc())
                .limit(limit)
            ).all()
        )
