from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.rag.quick_answer import QuickAnswerEngine


class QuickAnswerService:
    def __init__(self, db: Session, settings: Settings, embedder, chat_model, vector_store) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store

    def answer(self, knowledge_base_id: str, query: str, top_k: int | None = None):
        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        return QuickAnswerEngine(self.embedder, self.chat_model, self.vector_store).answer(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k or self.settings.quick_answer_top_k,
        )
