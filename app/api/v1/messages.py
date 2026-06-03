from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.chat import ChatRepository
from app.schemas.chat import ChatHistoryStats, MessageSearchRequest, MessageSearchResponse
from app.services.chat import ChatService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/search", response_model=MessageSearchResponse)
def search_messages(payload: MessageSearchRequest, db: DBSession, settings: AppSettings):
    try:
        return ChatService(ChatRepository(db), settings).search_messages(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/chat-history-stats", response_model=ChatHistoryStats)
def get_chat_history_stats(db: DBSession, settings: AppSettings):
    return ChatService(ChatRepository(db), settings).chat_history_stats()
