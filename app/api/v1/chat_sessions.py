from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatMessageListResponse,
    ChatSessionBatchDeleteRequest,
    ChatSessionBatchDeleteResponse,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionRead,
    ChatSessionUpdate,
    RecommendedQuestionListResponse,
)
from app.services.chat import ChatService, to_chat_message_read, to_chat_session_read

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=ChatSessionListResponse)
def list_chat_sessions(db: DBSession, settings: AppSettings, keyword: str | None = None):
    repo = ChatRepository(db)
    return ChatSessionListResponse(
        items=[to_chat_session_read(session) for session in repo.list_sessions(settings.default_tenant_id, keyword)]
    )


@router.post("", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_chat_session(payload: ChatSessionCreate, db: DBSession, settings: AppSettings):
    try:
        session = ChatService(ChatRepository(db), settings).create_session(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return to_chat_session_read(session)


@router.post("/batch-delete", response_model=ChatSessionBatchDeleteResponse)
def batch_delete_chat_sessions(payload: ChatSessionBatchDeleteRequest, db: DBSession, settings: AppSettings):
    return ChatService(ChatRepository(db), settings).batch_delete_sessions(payload.session_ids)


@router.get("/recommended-questions", response_model=RecommendedQuestionListResponse)
def list_recommended_questions(knowledge_base_id: str, db: DBSession, settings: AppSettings, limit: int = 6):
    try:
        items = ChatService(ChatRepository(db), settings).recommended_questions(
            knowledge_base_id=knowledge_base_id,
            limit=max(1, min(limit, 12)),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RecommendedQuestionListResponse(items=items)


@router.get("/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(session_id: str, db: DBSession, settings: AppSettings):
    repo = ChatRepository(db)
    session = repo.get_session(session_id, settings.default_tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    messages = repo.list_messages(session.id, settings.default_tenant_id)
    return ChatSessionDetail(
        **to_chat_session_read(session).model_dump(),
        messages=[to_chat_message_read(message) for message in messages],
    )


@router.patch("/{session_id}", response_model=ChatSessionRead)
def update_chat_session(session_id: str, payload: ChatSessionUpdate, db: DBSession, settings: AppSettings):
    repo = ChatRepository(db)
    session = repo.get_session(session_id, settings.default_tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    return to_chat_session_read(ChatService(repo, settings).update_session(session, payload))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(session_id: str, db: DBSession, settings: AppSettings):
    repo = ChatRepository(db)
    session = repo.get_session(session_id, settings.default_tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    repo.soft_delete_session(session)
    return None


@router.get("/{session_id}/messages", response_model=ChatMessageListResponse)
def list_chat_messages(session_id: str, db: DBSession, settings: AppSettings):
    repo = ChatRepository(db)
    session = repo.get_session(session_id, settings.default_tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    return ChatMessageListResponse(
        items=[to_chat_message_read(message) for message in repo.list_messages(session.id, settings.default_tenant_id)]
    )
