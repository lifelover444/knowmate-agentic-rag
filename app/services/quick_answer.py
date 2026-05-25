from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAIChatModel, OpenAIEmbedder
from app.rag.quick_answer import QuickAnswerEngine
from app.services.model_config import ModelConfigService


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
        embedder = self.embedder
        chat_model = self.chat_model
        if embedder is None or chat_model is None:
            runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config()
            embedder = embedder or OpenAIEmbedder(runtime_config)
            chat_model = chat_model or OpenAIChatModel(runtime_config)
        return QuickAnswerEngine(embedder, chat_model, self.vector_store).answer(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k or self.settings.quick_answer_top_k,
        )
