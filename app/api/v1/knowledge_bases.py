from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, get_settings
from app.core.config import Settings
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseRead
from app.services.knowledge_base import KnowledgeBaseService, normalize_chunking_config

router = APIRouter()

DBSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def to_read(kb, repo: KnowledgeBaseRepository, settings: Settings) -> KnowledgeBaseRead:
    document_count, chunk_count, processing_count = repo.counts(kb.id)
    return KnowledgeBaseRead.model_validate(
        {
            **kb.__dict__,
            "chunking_config": normalize_chunking_config(kb.chunking_config, settings),
            "document_count": document_count,
            "chunk_count": chunk_count,
            "processing_count": processing_count,
        }
    )


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    kb = KnowledgeBaseService(repo, settings).create(payload)
    return to_read(kb, repo, settings)


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: str,
    db: DBSession,
    settings: AppSettings,
):
    repo = KnowledgeBaseRepository(db)
    kb = repo.get(kb_id, settings.default_tenant_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return to_read(kb, repo, settings)
