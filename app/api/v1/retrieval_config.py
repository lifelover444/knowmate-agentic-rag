from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.retrieval import RetrievalConfigSchema
from app.services.retrieval_config import RetrievalConfigService

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=RetrievalConfigSchema)
def get_retrieval_config(db: DBSession, settings: AppSettings):
    return RetrievalConfigService(db, settings).get()


@router.put("", response_model=RetrievalConfigSchema)
def save_retrieval_config(payload: RetrievalConfigSchema, db: DBSession, settings: AppSettings):
    return RetrievalConfigService(db, settings).save(payload)
