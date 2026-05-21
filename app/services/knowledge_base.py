from app.core.config import Settings
from app.db.models import KnowledgeBase
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate


class KnowledgeBaseService:
    def __init__(self, repo: KnowledgeBaseRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def create(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        chunking = payload.chunking_config or {
            "chunk_size": self.settings.default_chunk_size,
            "chunk_overlap": self.settings.default_chunk_overlap,
        }
        if hasattr(chunking, "model_dump"):
            chunking = chunking.model_dump()
        return self.repo.create(
            KnowledgeBase(
                tenant_id=self.settings.default_tenant_id,
                name=payload.name,
                description=payload.description,
                chunking_config=chunking,
                embedding_model_id=self.settings.embedding_model,
                summary_model_id=self.settings.chat_model,
            )
        )
