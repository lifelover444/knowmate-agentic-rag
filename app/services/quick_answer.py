from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.llm_openai import OpenAIChatModel
from app.rag.prompt import build_quick_answer_messages
from app.rag.quick_answer import AnswerResult, AnswerSource
from app.services.knowledge_search import KnowledgeSearchService
from app.services.model_config import ModelConfigService


class QuickAnswerService:
    def __init__(self, db: Session, settings: Settings, embedder, chat_model, vector_store) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store

    def answer(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int | None = None,
        mode: str | None = None,
        enable_rerank: bool | None = None,
    ):
        hits = KnowledgeSearchService(self.db, self.settings, self.embedder, self.vector_store).search(
            knowledge_base_id=knowledge_base_id,
            query=query,
            mode=mode,
            top_k=top_k,
            enable_rerank=enable_rerank,
        )
        if not hits:
            return AnswerResult(answer="没有在知识库中找到可引用的内容。", sources=[])

        sources = [
            AnswerSource(
                document_id=hit.document_id,
                knowledge_base_id=hit.knowledge_base_id,
                chunk_id=hit.chunk_id,
                content=hit.content,
                score=hit.score,
                title=hit.title,
                context_header=hit.context_header,
                parent_chunk_id=hit.parent_chunk_id,
                chunk_type=hit.chunk_type,
                metadata=hit.metadata or {},
                retrieval_method=hit.retrieval_method,
                vector_score=hit.vector_score,
                keyword_score=hit.keyword_score,
                rrf_score=hit.rrf_score,
                rerank_score=hit.rerank_score,
                context_chunk_id=hit.context_chunk_id,
                context_content=hit.context_content,
            )
            for hit in hits
        ]
        chat_model = self.chat_model
        if chat_model is None:
            model_service = ModelConfigService(self.db, self.settings)
            from app.db.repositories.knowledge_base import KnowledgeBaseRepository

            kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
            if kb is None:
                raise LookupError("knowledge base not found")
            chat_model = OpenAIChatModel(
                model_service.build_runtime_config_for_model(kb.summary_model_id, "KnowledgeQA")
            )
        messages = build_quick_answer_messages(
            query=query,
            contexts=[
                f"{source.context_header}\n\n{source.context_content or source.content}"
                if source.context_header
                else source.context_content or source.content
                for source in sources
            ],
        )
        return AnswerResult(answer=chat_model.complete(messages), sources=sources)
