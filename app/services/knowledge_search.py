from dataclasses import replace

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAIEmbedder
from app.integrations.reranker import RerankerClient
from app.rag.retriever import (
    HybridRetriever,
    KeywordRetriever,
    ParentChildExpander,
    RerankPipeline,
    RetrievalHit,
    VectorRetriever,
)
from app.schemas.retrieval import RETRIEVAL_MODES, RetrievalConfigSchema
from app.services.model_config import ModelConfigService
from app.services.retrieval_config import RetrievalConfigService

RERANK_REQUIRED_MESSAGE = "启用重排需要先配置可用的 Rerank 模型"


class KnowledgeSearchService:
    def __init__(self, db: Session, settings: Settings, embedder, vector_store, reranker=None) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker

    def search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
    ) -> list[RetrievalHit]:
        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")

        config = RetrievalConfigService(self.db, self.settings).get()
        resolved_mode = mode or config.retrieval_mode
        if resolved_mode not in RETRIEVAL_MODES:
            raise ValueError("不支持的检索模式")
        limit = top_k or config.rerank_top_k
        retriever = self._build_retriever(kb.embedding_model_id, config, resolved_mode)
        hits = retriever.search(query, knowledge_base_id=knowledge_base_id, limit=config.embedding_top_k)
        hits = ParentChildExpander(ChunkRepository(self.db)).expand(hits)
        should_rerank = enable_rerank if enable_rerank is not None else config.enable_rerank
        if should_rerank:
            hits = self._rerank(query, hits, config)
        return _deduplicate_hits(hits)[:limit]

    def _build_retriever(self, embedding_model_id: str, config: RetrievalConfigSchema, mode: str):
        keyword = _ThresholdRetriever(KeywordRetriever(ChunkRepository(self.db)), config.keyword_threshold)
        if mode == "keyword_only":
            return keyword
        vector = _ThresholdRetriever(
            VectorRetriever(embedder=self._embedder(embedding_model_id), vector_store=self.vector_store),
            config.vector_threshold,
        )
        if mode == "vector_only":
            return vector
        return HybridRetriever(
            vector_retriever=vector,
            keyword_retriever=keyword,
            rrf_k=config.rrf_k,
            vector_weight=config.rrf_vector_weight,
            keyword_weight=config.rrf_keyword_weight,
        )

    def _embedder(self, embedding_model_id: str):
        if self.embedder is not None:
            return self.embedder
        runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config_for_model(
            embedding_model_id,
            "Embedding",
        )
        return OpenAIEmbedder(runtime_config)

    def _rerank(self, query: str, hits: list[RetrievalHit], config: RetrievalConfigSchema) -> list[RetrievalHit]:
        reranker = self.reranker
        if reranker is None:
            if not config.rerank_model_id:
                raise RuntimeError(RERANK_REQUIRED_MESSAGE)
            runtime_config = ModelConfigService(self.db, self.settings).build_runtime_config_for_model(
                config.rerank_model_id,
                "Rerank",
            )
            reranker = RerankerClient(runtime_config)
        return RerankPipeline(reranker, threshold=config.rerank_threshold, top_k=config.rerank_top_k).apply(query, hits)


def _deduplicate_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    by_chunk: dict[str, RetrievalHit] = {}
    for hit in hits:
        existing = by_chunk.get(hit.chunk_id)
        if existing is None or float(hit.score or 0) > float(existing.score or 0):
            by_chunk[hit.chunk_id] = hit
        elif existing.retrieval_method != hit.retrieval_method:
            by_chunk[hit.chunk_id] = replace(
                existing,
                vector_score=existing.vector_score or hit.vector_score,
                keyword_score=existing.keyword_score or hit.keyword_score,
                rrf_score=existing.rrf_score or hit.rrf_score,
            )
    return sorted(by_chunk.values(), key=lambda item: float(item.score or 0), reverse=True)


class _ThresholdRetriever:
    def __init__(self, retriever, threshold: float | None) -> None:
        self.retriever = retriever
        self.threshold = threshold

    def search(self, query: str, *, knowledge_base_id: str, limit: int, score_threshold: float | None = None):
        threshold = self.threshold if score_threshold is None else score_threshold
        return self.retriever.search(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            score_threshold=threshold,
        )
