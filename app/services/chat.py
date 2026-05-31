from datetime import UTC, datetime

from app.core.config import Settings
from app.db.models import ChatMessage, ChatSession
from app.db.repositories.chat import ChatRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.chat import ChatMessageRead, ChatSessionCreate, ChatSessionRead, ChatSessionUpdate
from app.schemas.quick_answer import SourceRead


def to_chat_session_read(session: ChatSession) -> ChatSessionRead:
    return ChatSessionRead(
        id=session.id,
        tenant_id=session.tenant_id,
        knowledge_base_id=session.knowledge_base_id,
        title=session.title,
        is_pinned=session.is_pinned,
        settings=session.settings_json or {},
        last_message_at=session.last_message_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def to_chat_message_read(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        tenant_id=message.tenant_id,
        session_id=message.session_id,
        role=message.role,  # type: ignore[arg-type]
        content=message.content,
        original_query=message.original_query,
        rewritten_query=message.rewritten_query,
        sources=[SourceRead.model_validate(source) for source in (message.sources_json or [])],
        retrieval_trace=message.retrieval_trace_json,
        model_config_info=message.model_config_json,
        status=message.status,
        error_message=message.error_message,
        created_at=message.created_at,
    )


class ChatService:
    def __init__(self, repo: ChatRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def create_session(self, payload: ChatSessionCreate) -> ChatSession:
        tenant_id = self.settings.default_tenant_id
        if KnowledgeBaseRepository(self.repo.db).get(payload.knowledge_base_id, tenant_id) is None:
            raise LookupError("knowledge base not found")
        now = datetime.now(UTC)
        session = ChatSession(
            tenant_id=tenant_id,
            knowledge_base_id=payload.knowledge_base_id,
            title=(payload.title or "新会话").strip()[:255] or "新会话",
            is_pinned=False,
            settings_json=payload.settings.model_dump(exclude_none=True) if payload.settings else {},
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        return self.repo.create_session(session)

    def update_session(self, session: ChatSession, payload: ChatSessionUpdate) -> ChatSession:
        if payload.title is not None:
            session.title = payload.title.strip()[:255] or session.title
        if payload.is_pinned is not None:
            session.is_pinned = payload.is_pinned
        if payload.settings is not None:
            session.settings_json = payload.settings.model_dump(exclude_none=True)
        session.updated_at = datetime.now(UTC)
        return self.repo.save_session(session)

    def create_user_message(self, session: ChatSession, content: str) -> ChatMessage:
        now = datetime.now(UTC)
        session.last_message_at = now
        session.updated_at = now
        self.repo.save_session(session)
        return self.repo.create_message(
            ChatMessage(
                tenant_id=session.tenant_id,
                session_id=session.id,
                role="user",
                content=content,
                original_query=content,
                status="completed",
                created_at=now,
            )
        )

    def create_assistant_message(
        self,
        session: ChatSession,
        *,
        content: str,
        original_query: str,
        rewritten_query: str | None,
        sources: list[dict],
        retrieval_trace: dict,
        model_config: dict,
        status: str = "completed",
        error_message: str | None = None,
    ) -> ChatMessage:
        now = datetime.now(UTC)
        session.last_message_at = now
        session.updated_at = now
        self.repo.save_session(session)
        return self.repo.create_message(
            ChatMessage(
                tenant_id=session.tenant_id,
                session_id=session.id,
                role="assistant",
                content=content,
                original_query=original_query,
                rewritten_query=rewritten_query,
                sources_json=sources,
                retrieval_trace_json=retrieval_trace,
                model_config_json=model_config,
                status=status,
                error_message=error_message,
                created_at=now,
            )
        )
