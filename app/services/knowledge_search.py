from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Knowledge
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
from app.services.knowledge_base import normalize_indexing_strategy
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
        knowledge_base_id: str | None = None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
    ) -> list[RetrievalHit]:
        repo = KnowledgeBaseRepository(self.db)
        scope = self._resolve_scope(repo, knowledge_base_id, knowledge_base_ids or [], knowledge_ids or [])
        if not scope:
            raise ValueError("至少提供一个 knowledge_base_id、knowledge_base_ids 或 knowledge_ids")
        kbs = [repo.get(kb_id, self.settings.default_tenant_id) for kb_id in scope]
        if any(kb is None for kb in kbs):
            raise LookupError("knowledge base not found")
        resolved_kbs = [kb for kb in kbs if kb is not None]
        _validate_same_embedding_model(resolved_kbs)

        config = RetrievalConfigService(self.db, self.settings).get()
        resolved_mode = mode or config.retrieval_mode
        if resolved_mode not in RETRIEVAL_MODES:
            raise ValueError("不支持的检索模式")
        limit = top_k or config.rerank_top_k
        hits: list[RetrievalHit] = []
        knowledge_ids_by_kb = _knowledge_ids_by_kb(self.db, knowledge_ids or [])
        for kb in resolved_kbs:
            strategy = normalize_indexing_strategy(kb.indexing_strategy)
            _validate_mode_allowed(resolved_mode, strategy)
            retriever = self._build_retriever(kb.embedding_model_id, config, resolved_mode)
            scoped_knowledge_ids = knowledge_ids_by_kb.get(kb.id) if knowledge_ids else None
            if knowledge_ids and not scoped_knowledge_ids:
                continue
            kb_hits = retriever.search(
                query,
                knowledge_base_id=kb.id,
                limit=config.embedding_top_k,
                knowledge_ids=scoped_knowledge_ids,
            )
            hits.extend(replace(hit, knowledge_base_name=kb.name) for hit in kb_hits)
        hits = ParentChildExpander(ChunkRepository(self.db)).expand(hits)
        should_rerank = enable_rerank if enable_rerank is not None else config.enable_rerank
        if should_rerank:
            if any(not normalize_indexing_strategy(kb.indexing_strategy)["enable_rerank"] for kb in resolved_kbs):
                raise ValueError("当前知识库未启用重排")
            hits = self._rerank(query, hits, config)
        return _deduplicate_hits(hits)[:limit]

    def _resolve_scope(
        self,
        repo: KnowledgeBaseRepository,
        knowledge_base_id: str | None,
        knowledge_base_ids: list[str],
        knowledge_ids: list[str],
    ) -> list[str]:
        scoped_ids: list[str] = []
        for kb_id in [knowledge_base_id, *knowledge_base_ids]:
            if kb_id and kb_id not in scoped_ids:
                scoped_ids.append(kb_id)
        if knowledge_ids:
            document_rows = list(
                self.db.scalars(
                    select(Knowledge).where(
                        Knowledge.id.in_(knowledge_ids),
                        Knowledge.tenant_id == self.settings.default_tenant_id,
                        Knowledge.deleted_at.is_(None),
                    )
                ).all()
            )
            if len(document_rows) != len(set(knowledge_ids)):
                raise LookupError("knowledge not found")
            for document in document_rows:
                if repo.get(document.knowledge_base_id, self.settings.default_tenant_id) is None:
                    raise LookupError("knowledge base not found")
                if document.knowledge_base_id not in scoped_ids:
                    scoped_ids.append(document.knowledge_base_id)
        return scoped_ids

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


def _validate_mode_allowed(mode: str, strategy: dict) -> None:
    if mode == "vector_only" and not strategy["enable_vector"]:
        raise ValueError("当前知识库未启用向量检索")
    if mode == "keyword_only" and not strategy["enable_keyword"]:
        raise ValueError("当前知识库未启用关键词检索")
    if mode == "hybrid" and not (strategy["enable_vector"] and strategy["enable_keyword"]):
        raise ValueError("混合检索需要同时启用向量检索和关键词检索")


class _ThresholdRetriever:
    def __init__(self, retriever, threshold: float | None) -> None:
        self.retriever = retriever
        self.threshold = threshold

    def search(
        self,
        query: str,
        *,
        knowledge_base_id: str,
        limit: int,
        score_threshold: float | None = None,
        knowledge_ids: list[str] | None = None,
    ):
        threshold = self.threshold if score_threshold is None else score_threshold
        return self.retriever.search(
            query,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            score_threshold=threshold,
            knowledge_ids=knowledge_ids,
        )


def _knowledge_ids_by_kb(db: Session, knowledge_ids: list[str]) -> dict[str, list[str]]:
    if not knowledge_ids:
        return {}
    rows = list(
        db.scalars(
            select(Knowledge).where(
                Knowledge.id.in_(knowledge_ids),
                Knowledge.deleted_at.is_(None),
            )
        ).all()
    )
    grouped: dict[str, list[str]] = {}
    for document in rows:
        grouped.setdefault(document.knowledge_base_id, []).append(document.id)
    return grouped


def _validate_same_embedding_model(kbs) -> None:
    model_ids = {kb.embedding_model_id for kb in kbs if kb.embedding_model_id}
    if len(model_ids) > 1:
        raise ValueError("跨知识库检索要求使用相同 Embedding 模型")
