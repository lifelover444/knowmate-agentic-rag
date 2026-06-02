from datetime import UTC, datetime

from app.core.config import Settings
from app.db.models import ChatMessage, ChatSession, Chunk, FAQEntry, Knowledge
from app.db.repositories.chat import ChatRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.chat import (
    ChatMessageRead,
    ChatSessionBatchDeleteFailure,
    ChatSessionBatchDeleteResponse,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionUpdate,
    RecommendedQuestionRead,
)
from app.schemas.quick_answer import SourceRead


def to_chat_session_read(session: ChatSession) -> ChatSessionRead:
    settings_json = session.settings_json or {}
    return ChatSessionRead(
        id=session.id,
        tenant_id=session.tenant_id,
        knowledge_base_id=session.knowledge_base_id,
        title=session.title,
        is_pinned=session.is_pinned,
        settings=settings_json,
        last_request_state=settings_json.get("last_request_state") or {},
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
        mentioned_items=(message.model_config_json or {}).get("mentioned_items") or [],
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

    def update_last_request_state(self, session: ChatSession, state: dict) -> ChatSession:
        settings_json = dict(session.settings_json or {})
        settings_json["last_request_state"] = state
        session.settings_json = settings_json
        session.updated_at = datetime.now(UTC)
        return self.repo.save_session(session)

    def maybe_auto_title(self, session: ChatSession, query: str, history_count: int) -> ChatSession:
        if history_count:
            return session
        if session.title.strip() not in {"", "新会话"} and not session.title.strip().endswith("会话"):
            return session
        title = _title_from_query(query)
        if not title:
            return session
        session.title = title
        session.updated_at = datetime.now(UTC)
        return self.repo.save_session(session)

    def batch_delete_sessions(self, session_ids: list[str]) -> ChatSessionBatchDeleteResponse:
        tenant_id = self.settings.default_tenant_id
        seen: set[str] = set()
        sessions: list[ChatSession] = []
        failures: list[ChatSessionBatchDeleteFailure] = []
        for session_id in session_ids:
            if session_id in seen:
                continue
            seen.add(session_id)
            session = self.repo.get_session(session_id, tenant_id)
            if session is None:
                failures.append(
                    ChatSessionBatchDeleteFailure(session_id=session_id, reason="chat session not found")
                )
                continue
            sessions.append(session)

        if sessions:
            self.repo.soft_delete_sessions(sessions)

        return ChatSessionBatchDeleteResponse(
            requested=len(session_ids),
            deleted=len(sessions),
            failed=len(failures),
            failures=failures,
        )

    def recommended_questions(self, knowledge_base_id: str, limit: int = 6) -> list[RecommendedQuestionRead]:
        tenant_id = self.settings.default_tenant_id
        if KnowledgeBaseRepository(self.repo.db).get(knowledge_base_id, tenant_id) is None:
            raise LookupError("knowledge base not found")

        questions: list[RecommendedQuestionRead] = []
        seen: set[str] = set()

        def add(item: RecommendedQuestionRead) -> None:
            key = item.question.strip()
            if not key or key in seen or len(questions) >= limit:
                return
            seen.add(key)
            questions.append(item)

        for faq in self.repo.list_recommended_faqs(knowledge_base_id, tenant_id, limit):
            add(self._question_from_faq(faq))

        for chunk, knowledge in self.repo.list_recommended_chunks(knowledge_base_id, tenant_id, limit * 3):
            for item in self._questions_from_chunk(chunk, knowledge):
                add(item)
                if len(questions) >= limit:
                    break
            if len(questions) >= limit:
                break

        return questions

    def create_user_message(
        self,
        session: ChatSession,
        content: str,
        mentioned_items: list[dict] | None = None,
    ) -> ChatMessage:
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
                model_config_json={"mentioned_items": mentioned_items or []},
                status="completed",
                created_at=now,
            )
        )

    def _question_from_faq(self, faq: FAQEntry) -> RecommendedQuestionRead:
        return RecommendedQuestionRead(
            question=faq.question.strip(),
            source_type="faq",
            knowledge_base_id=faq.knowledge_base_id,
            knowledge_id=faq.knowledge_id,
            faq_id=faq.id,
            title="FAQ",
        )

    def _questions_from_chunk(self, chunk: Chunk, knowledge: Knowledge) -> list[RecommendedQuestionRead]:
        generated = self._extract_generated_questions(chunk.chunk_metadata or {})
        if not generated:
            generated = [self._fallback_question(chunk, knowledge)]
        return [
            RecommendedQuestionRead(
                question=question,
                source_type="chunk",
                knowledge_base_id=chunk.knowledge_base_id,
                knowledge_id=chunk.knowledge_id,
                chunk_id=chunk.id,
                title=knowledge.title,
            )
            for question in generated
            if question
        ]

    def _extract_generated_questions(self, metadata: dict) -> list[str]:
        raw_questions = metadata.get("generated_questions") if isinstance(metadata, dict) else None
        if not isinstance(raw_questions, list):
            return []
        questions: list[str] = []
        for raw in raw_questions:
            if isinstance(raw, str):
                question = raw.strip()
            elif isinstance(raw, dict):
                question = str(raw.get("question") or raw.get("content") or "").strip()
            else:
                question = ""
            if question:
                questions.append(question[:180])
        return questions

    def _fallback_question(self, chunk: Chunk, knowledge: Knowledge) -> str:
        topic = (chunk.context_header or knowledge.title or chunk.content[:30]).strip()
        topic = " ".join(topic.split())[:48]
        return f"关于{topic}，有哪些要点？" if topic else ""

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


def _title_from_query(query: str) -> str:
    title = " ".join((query or "").strip().split())
    title = title.rstrip("？?。.!！；;：:")
    return title[:28] or "新会话"
