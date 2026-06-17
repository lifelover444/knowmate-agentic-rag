import re
import time
from dataclasses import dataclass, replace

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
    tokenize_query,
)
from app.schemas.retrieval import RETRIEVAL_MODES, RetrievalConfigSchema
from app.services.knowledge_base import normalize_indexing_strategy
from app.services.model_config import ModelConfigService
from app.services.retrieval_config import RetrievalConfigService

RERANK_REQUIRED_MESSAGE = "系统未完成 rerank 模型配置，请先在模型配置中配置可用的重排模型。"
FAQ_BOOST_MIN_SCORE = 0.8
FAQ_BOOST_FACTOR = 1.2


@dataclass
class KnowledgeSearchResult:
    hits: list[RetrievalHit]
    diagnostics: dict


class KnowledgeSearchService:
    def __init__(self, db: Session, settings: Settings, embedder, vector_store, reranker=None) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker
        self._last_rerank_diagnostics: dict = {}
        self._last_expansion_diagnostics: dict = {
            "status": "skipped",
            "input": {},
            "output": {"reason": "not_run", "variants": [], "added_hit_count": 0},
        }

    def search(
        self,
        *,
        knowledge_base_id: str | None = None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
        query: str,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
    ) -> list[RetrievalHit]:
        return self.search_with_diagnostics(
            knowledge_base_id=knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_ids=knowledge_ids,
            query=query,
            top_k=top_k,
            enable_rerank=enable_rerank,
        ).hits

    def search_with_diagnostics(
        self,
        *,
        knowledge_base_id: str | None = None,
        knowledge_base_ids: list[str] | None = None,
        knowledge_ids: list[str] | None = None,
        query: str,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
    ) -> KnowledgeSearchResult:
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
        resolved_mode = config.retrieval_mode
        if resolved_mode not in RETRIEVAL_MODES:
            raise ValueError("不支持的检索模式")
        limit = top_k or config.rerank_top_k
        over_retrieval_limit = _over_retrieval_limit(config, scope_count=len(resolved_kbs))
        should_rerank = bool(config.enable_rerank)
        diagnostics = _DiagnosticsBuilder(
            query=query,
            mode=resolved_mode,
            requested_top_k=top_k,
            effective_top_k=limit,
            over_retrieval_limit=over_retrieval_limit,
            knowledge_base_ids=[kb.id for kb in resolved_kbs],
            knowledge_ids=knowledge_ids or [],
            enable_rerank=config.enable_rerank,
        )
        hits: list[RetrievalHit] = []
        knowledge_ids_by_kb = _knowledge_ids_by_kb(self.db, knowledge_ids or [])
        composite_retriever = self._build_composite_retriever()
        for kb in resolved_kbs:
            strategy = normalize_indexing_strategy(kb.indexing_strategy)
            _validate_mode_allowed(resolved_mode, strategy)
            scoped_knowledge_ids = knowledge_ids_by_kb.get(kb.id) if knowledge_ids else None
            if knowledge_ids and not scoped_knowledge_ids:
                continue
            retriever_started = time.perf_counter()
            try:
                kb_hits = composite_retriever.search_kb(
                    query,
                    kb=kb,
                    config=config,
                    over_retrieval_limit=over_retrieval_limit,
                    mode=resolved_mode,
                    diagnostics=diagnostics,
                    knowledge_ids=scoped_knowledge_ids,
                )
            except Exception as exc:
                diagnostics.add_retriever(
                    knowledge_base_id=kb.id,
                    knowledge_base_name=kb.name,
                    engine=composite_retriever.engine,
                    vector_engine=composite_retriever.vector_engine,
                    keyword_engine=composite_retriever.keyword_engine,
                    mode=resolved_mode,
                    status="failed",
                    hit_count=0,
                    duration_ms=_duration_ms(retriever_started),
                    error_message=str(exc),
                )
                raise
            diagnostics.add_retriever(
                knowledge_base_id=kb.id,
                knowledge_base_name=kb.name,
                engine=composite_retriever.engine,
                vector_engine=composite_retriever.vector_engine,
                keyword_engine=composite_retriever.keyword_engine,
                mode=resolved_mode,
                status="done",
                hit_count=len(kb_hits),
                duration_ms=_duration_ms(retriever_started),
            )
            hits.extend(replace(hit, knowledge_base_name=kb.name) for hit in kb_hits)
        expansion_hits = self._expand_low_recall_query(
            query=query,
            current_hits=hits,
            resolved_kbs=resolved_kbs,
            config=config,
            over_retrieval_limit=over_retrieval_limit,
            knowledge_ids_by_kb=knowledge_ids_by_kb,
            has_knowledge_filter=bool(knowledge_ids),
        )
        if expansion_hits:
            hits.extend(expansion_hits)
        expansion_stage = self._last_expansion_diagnostics
        diagnostics.add_stage(
            "query_expansion",
            expansion_stage["status"],
            input_summary=expansion_stage["input"],
            output_summary=expansion_stage["output"],
        )
        deduplicate_input_count = len(hits)
        hits = diagnostics.run_stage(
            "deduplicate",
            "done",
            input_summary={"hit_count": deduplicate_input_count},
            action=lambda: _deduplicate_hits(hits),
            output_summary=lambda deduplicated: {
                "input_count": deduplicate_input_count,
                "output_count": len(deduplicated),
                "removed_count": max(0, deduplicate_input_count - len(deduplicated)),
            },
        )
        faq_merge_input_count = len(hits)
        hits = diagnostics.run_stage(
            "faq_merge",
            "done",
            input_summary={
                "candidate_count": faq_merge_input_count,
                "faq_count": sum(1 for hit in hits if _is_faq_hit(hit)),
                "min_boost_score": FAQ_BOOST_MIN_SCORE,
                "boost_factor": FAQ_BOOST_FACTOR,
            },
            action=lambda: _merge_faq_hits(hits),
            output_summary=lambda merged: {
                "input_count": faq_merge_input_count,
                "output_count": len(merged),
                "faq_count": sum(1 for hit in merged if _is_faq_hit(hit)),
                "boost_count": sum(1 for hit in merged if (hit.metadata or {}).get("faq_boosted") is True),
                "max_boost_factor": max(
                    [
                        float((hit.metadata or {}).get("faq_boost_factor") or 1)
                        for hit in merged
                        if (hit.metadata or {}).get("faq_boosted") is True
                    ],
                    default=1,
                ),
            },
        )
        if should_rerank:
            if any(not normalize_indexing_strategy(kb.indexing_strategy)["enable_rerank"] for kb in resolved_kbs):
                raise ValueError("当前知识库未启用重排")
            if hits:
                rerank_input_count = len(hits)
                rerank_started = time.perf_counter()
                rerank_input = {"candidate_count": rerank_input_count, "threshold": config.rerank_threshold}
                try:
                    hits = self._rerank(query, hits, config)
                except Exception as exc:
                    diagnostics.add_stage(
                        "rerank",
                        "failed",
                        duration_ms=_duration_ms(rerank_started),
                        input_summary=rerank_input,
                        output_summary={
                            "rerank_input_count": rerank_input_count,
                            "rerank_output_count": 0,
                            "fallback": False,
                        },
                        error_message=str(exc),
                    )
                    raise
                else:
                    rerank_diagnostics = dict(self._last_rerank_diagnostics)
                    diagnostics.add_stage(
                        "rerank",
                        "done",
                        duration_ms=_duration_ms(rerank_started),
                        input_summary=rerank_input,
                        output_summary={
                            "rerank_input_count": rerank_input_count,
                            "rerank_output_count": len(hits),
                            "model_config_used": config.rerank_model_id or "injected",
                            "threshold": config.rerank_threshold,
                            "fallback": False,
                            **rerank_diagnostics,
                        },
                    )
            else:
                diagnostics.add_stage(
                    "rerank",
                    "skipped",
                    input_summary={"candidate_count": 0},
                    output_summary={"reason": "no_hits"},
                )
        else:
            rerank_skip_output = {"enabled": False}
            if config.enable_rerank and not (config.rerank_model_id or self.reranker is not None):
                rerank_skip_output = {"enabled": True, "reason": "missing_rerank_model"}
            diagnostics.add_stage(
                "rerank",
                "skipped",
                input_summary={"candidate_count": len(hits)},
                output_summary=rerank_skip_output,
            )
        parent_input_count = len(hits)
        hits = diagnostics.run_stage(
            "parent_expand",
            "done",
            input_summary={"hit_count": parent_input_count},
            action=lambda: ParentChildExpander(ChunkRepository(self.db)).expand(hits),
            output_summary=lambda expanded: {
                "input_count": parent_input_count,
                "output_count": len(expanded),
                "expanded_count": sum(1 for hit in expanded if hit.context_chunk_id),
            },
        )
        final_hits = hits[:limit]
        diagnostics.finish(final_hit_count=len(final_hits))
        return KnowledgeSearchResult(hits=final_hits, diagnostics=diagnostics.to_dict())

    def _search_kb_with_diagnostics(
        self,
        query: str,
        *,
        kb,
        config: RetrievalConfigSchema,
        over_retrieval_limit: int,
        mode: str,
        diagnostics,
        knowledge_ids: list[str] | None,
    ) -> list[RetrievalHit]:
        vector_hits: list[RetrievalHit] = []
        keyword_hits: list[RetrievalHit] = []
        if mode in {"vector_only", "hybrid"}:
            vector = _ThresholdRetriever(
                VectorRetriever(embedder=self._embedder(kb.embedding_model_id), vector_store=self.vector_store),
                config.vector_threshold,
            )
            vector_limit = max(config.embedding_top_k, over_retrieval_limit)
            vector_hits = diagnostics.run_stage(
                "vector",
                "done",
                input_summary={
                    "knowledge_base_id": kb.id,
                    "limit": vector_limit,
                    "configured_limit": config.embedding_top_k,
                    "over_retrieval_limit": over_retrieval_limit,
                    "threshold": config.vector_threshold,
                    "knowledge_ids": knowledge_ids or [],
                },
                action=lambda: _filter_answer_candidate_hits(
                    vector.search(
                        query,
                        knowledge_base_id=kb.id,
                        limit=vector_limit,
                        knowledge_ids=knowledge_ids,
                    )
                ),
                output_summary=lambda found: {"hit_count": len(found), "knowledge_base_id": kb.id},
                aggregate_output_keys=("hit_count",),
            )
        else:
            diagnostics.add_stage(
                "vector",
                "skipped",
                input_summary={"knowledge_base_id": kb.id, "mode": mode},
                output_summary={"reason": "mode_not_applicable"},
            )

        if mode in {"keyword_only", "hybrid"}:
            keyword = _ThresholdRetriever(KeywordRetriever(ChunkRepository(self.db)), config.keyword_threshold)
            keyword_limit = max(config.keyword_top_k, over_retrieval_limit)
            keyword_hits = diagnostics.run_stage(
                "keyword",
                "done",
                input_summary={
                    "knowledge_base_id": kb.id,
                    "limit": keyword_limit,
                    "configured_limit": config.keyword_top_k,
                    "over_retrieval_limit": over_retrieval_limit,
                    "threshold": config.keyword_threshold,
                    "knowledge_ids": knowledge_ids or [],
                },
                action=lambda: _filter_answer_candidate_hits(
                    keyword.search(
                        query,
                        knowledge_base_id=kb.id,
                        limit=keyword_limit,
                        knowledge_ids=knowledge_ids,
                    )
                ),
                output_summary=lambda found: {"hit_count": len(found), "knowledge_base_id": kb.id},
                aggregate_output_keys=("hit_count",),
            )
        else:
            diagnostics.add_stage(
                "keyword",
                "skipped",
                input_summary={"knowledge_base_id": kb.id, "mode": mode},
                output_summary={"reason": "mode_not_applicable"},
            )

        if mode == "hybrid":
            rrf_limit = max(config.rrf_top_k, over_retrieval_limit)
            return diagnostics.run_stage(
                "rrf",
                "done",
                input_summary={
                    "knowledge_base_id": kb.id,
                    "vector_count": len(vector_hits),
                    "keyword_count": len(keyword_hits),
                    "rrf_k": config.rrf_k,
                    "limit": rrf_limit,
                    "configured_limit": config.rrf_top_k,
                    "over_retrieval_limit": over_retrieval_limit,
                },
                action=lambda: _merge_rrf(
                    vector_hits,
                    keyword_hits,
                    rrf_k=config.rrf_k,
                    vector_weight=config.rrf_vector_weight,
                    keyword_weight=config.rrf_keyword_weight,
                    limit=rrf_limit,
                ),
                output_summary=lambda merged: {
                    "input_count": len(vector_hits) + len(keyword_hits),
                    "output_count": len(merged),
                    "knowledge_base_id": kb.id,
                },
                aggregate_output_keys=("input_count", "output_count"),
            )
        diagnostics.add_stage(
            "rrf",
            "skipped",
            input_summary={
                "knowledge_base_id": kb.id,
                "vector_count": len(vector_hits),
                "keyword_count": len(keyword_hits),
            },
            output_summary={"reason": "mode_not_applicable"},
        )
        return vector_hits if mode == "vector_only" else keyword_hits

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

    def _build_composite_retriever(self):
        return CompositeKnowledgeRetriever(self)

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
        pipeline = RerankPipeline(reranker, threshold=config.rerank_threshold, top_k=config.rerank_top_k)
        result = pipeline.apply(query, hits)
        self._last_rerank_diagnostics = pipeline.diagnostics
        return result

    def _expand_low_recall_query(
        self,
        *,
        query: str,
        current_hits: list[RetrievalHit],
        resolved_kbs,
        config: RetrievalConfigSchema,
        over_retrieval_limit: int,
        knowledge_ids_by_kb: dict[str, list[str]],
        has_knowledge_filter: bool,
    ) -> list[RetrievalHit]:
        threshold = min(config.rerank_top_k, over_retrieval_limit)
        if len(current_hits) >= threshold:
            self._last_expansion_diagnostics = {
                "status": "skipped",
                "input": {"hit_count": len(current_hits), "threshold": threshold},
                "output": {"reason": "enough_hits", "variants": [], "added_hit_count": 0},
            }
            return []
        variants = _expand_query_variants(query)
        if not variants:
            self._last_expansion_diagnostics = {
                "status": "skipped",
                "input": {"hit_count": len(current_hits), "threshold": threshold},
                "output": {"reason": "no_variants", "variants": [], "added_hit_count": 0},
            }
            return []
        lowered_threshold = round(max(config.keyword_threshold * 0.8, 0.0), 4)
        keyword = _ThresholdRetriever(KeywordRetriever(ChunkRepository(self.db)), lowered_threshold)
        expanded: list[RetrievalHit] = []
        expanded_by_chunk_id: dict[str, RetrievalHit] = {}
        for variant in variants:
            for kb in resolved_kbs:
                scoped_knowledge_ids = knowledge_ids_by_kb.get(kb.id) if has_knowledge_filter else None
                if has_knowledge_filter and not scoped_knowledge_ids:
                    continue
                found = keyword.search(
                    variant,
                    knowledge_base_id=kb.id,
                    limit=over_retrieval_limit,
                    knowledge_ids=scoped_knowledge_ids,
                )
                for hit in found:
                    if hit.chunk_type == "parent":
                        continue
                    expanded_hit = replace(hit, knowledge_base_name=kb.name, retrieval_method="keyword_expansion")
                    existing = expanded_by_chunk_id.get(expanded_hit.chunk_id)
                    if existing is None or float(expanded_hit.score or 0) > float(existing.score or 0):
                        expanded_by_chunk_id[expanded_hit.chunk_id] = expanded_hit
        expanded = sorted(expanded_by_chunk_id.values(), key=lambda item: float(item.score or 0), reverse=True)
        self._last_expansion_diagnostics = {
            "status": "done",
            "input": {
                "hit_count": len(current_hits),
                "threshold": threshold,
                "keyword_threshold": config.keyword_threshold,
            },
            "output": {
                "variants": variants,
                "lowered_keyword_threshold": lowered_threshold,
                "added_hit_count": len(expanded),
                "before_count": len(current_hits),
                "after_count": len(current_hits) + len(expanded),
            },
        }
        return expanded


def _deduplicate_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    by_chunk: dict[str, RetrievalHit] = {}
    for hit in hits:
        existing = by_chunk.get(hit.chunk_id)
        if existing is None or float(hit.score or 0) > float(existing.score or 0):
            if existing is not None and _is_expansion_hit(hit) and not _is_expansion_hit(existing):
                by_chunk[hit.chunk_id] = replace(
                    existing,
                    keyword_score=existing.keyword_score or hit.keyword_score,
                    rrf_score=existing.rrf_score or hit.rrf_score,
                )
                continue
            by_chunk[hit.chunk_id] = hit
        elif existing.retrieval_method != hit.retrieval_method:
            by_chunk[hit.chunk_id] = replace(
                existing,
                vector_score=existing.vector_score or hit.vector_score,
                keyword_score=existing.keyword_score or hit.keyword_score,
                rrf_score=existing.rrf_score or hit.rrf_score,
            )
    return sorted(by_chunk.values(), key=lambda item: float(item.score or 0), reverse=True)


def _filter_answer_candidate_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    return [hit for hit in hits if hit.chunk_type != "parent"]


def _is_expansion_hit(hit: RetrievalHit) -> bool:
    return hit.retrieval_method == "keyword_expansion"


def _merge_faq_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    merged: list[RetrievalHit] = []
    for hit in hits:
        confidence_score = max(float(value or 0) for value in (hit.score, hit.vector_score, hit.keyword_score))
        if not _is_faq_hit(hit) or confidence_score < FAQ_BOOST_MIN_SCORE:
            merged.append(hit)
            continue
        original_score = confidence_score
        boosted_score = min(original_score * FAQ_BOOST_FACTOR, 1.0)
        metadata = dict(hit.metadata or {})
        metadata.update(
            {
                "faq_boosted": True,
                "faq_original_score": round(original_score, 6),
                "faq_boost_factor": FAQ_BOOST_FACTOR,
            }
        )
        merged.append(replace(hit, score=boosted_score, metadata=metadata))
    return sorted(merged, key=lambda item: float(item.score or 0), reverse=True)


def _is_faq_hit(hit: RetrievalHit) -> bool:
    metadata = hit.metadata or {}
    return hit.chunk_type == "faq" or metadata.get("source_type") == "faq"


def _merge_rrf(
    vector_hits: list[RetrievalHit],
    keyword_hits: list[RetrievalHit],
    *,
    rrf_k: int,
    vector_weight: float,
    keyword_weight: float,
    limit: int,
) -> list[RetrievalHit]:
    merged: dict[str, RetrievalHit] = {}
    rrf_scores: dict[str, float] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        merged[hit.chunk_id] = hit
        rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + vector_weight / (rrf_k + rank)
    for rank, hit in enumerate(keyword_hits, start=1):
        existing = merged.get(hit.chunk_id)
        if existing is None:
            merged[hit.chunk_id] = hit
        else:
            merged[hit.chunk_id] = replace(existing, keyword_score=hit.keyword_score or hit.score)
        rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + keyword_weight / (rrf_k + rank)

    results = [
        replace(
            hit,
            retrieval_method="hybrid" if hit.chunk_id in rrf_scores else hit.retrieval_method,
            score=rrf_scores.get(hit.chunk_id, hit.score),
            rrf_score=rrf_scores.get(hit.chunk_id),
            vector_score=hit.vector_score,
            keyword_score=hit.keyword_score,
        )
        for hit in merged.values()
    ]
    results.sort(key=lambda item: float(item.rrf_score or item.score or 0), reverse=True)
    return results[:limit]


class _DiagnosticsBuilder:
    def __init__(
        self,
        *,
        query: str,
        mode: str,
        requested_top_k: int | None,
        effective_top_k: int,
        over_retrieval_limit: int,
        knowledge_base_ids: list[str],
        knowledge_ids: list[str],
        enable_rerank: bool,
    ) -> None:
        self.payload = {
            "query": query,
            "mode": mode,
            "requested_top_k": requested_top_k,
            "effective_top_k": effective_top_k,
            "over_retrieval_limit": over_retrieval_limit,
            "knowledge_base_ids": knowledge_base_ids,
            "knowledge_ids": knowledge_ids,
            "enable_rerank": enable_rerank,
            "retrievers": [],
            "stages": [],
        }
        self._stage_index: dict[str, dict] = {}

    def add_retriever(
        self,
        *,
        knowledge_base_id: str,
        knowledge_base_name: str,
        engine: str,
        vector_engine: str | None = None,
        keyword_engine: str | None = None,
        mode: str,
        status: str,
        hit_count: int,
        duration_ms: int,
        error_message: str | None = None,
    ) -> None:
        item = {
            "knowledge_base_id": knowledge_base_id,
            "knowledge_base_name": knowledge_base_name,
            "engine": engine,
            "vector_engine": vector_engine,
            "keyword_engine": keyword_engine,
            "mode": mode,
            "status": status,
            "hit_count": hit_count,
            "duration_ms": duration_ms,
        }
        if error_message:
            item["error_message"] = error_message
        self.payload["retrievers"].append(item)

    def run_stage(
        self,
        name: str,
        status: str,
        *,
        input_summary: dict,
        action,
        output_summary,
        aggregate_output_keys: tuple[str, ...] = (),
    ):
        started_at = time.perf_counter()
        try:
            result = action()
        except Exception as exc:
            self.add_stage(
                name,
                "failed",
                duration_ms=_duration_ms(started_at),
                input_summary=input_summary,
                output_summary={},
                error_message=str(exc),
                aggregate_output_keys=aggregate_output_keys,
            )
            raise
        self.add_stage(
            name,
            status,
            duration_ms=_duration_ms(started_at),
            input_summary=input_summary,
            output_summary=output_summary(result),
            aggregate_output_keys=aggregate_output_keys,
        )
        return result

    def add_stage(
        self,
        name: str,
        status: str,
        *,
        input_summary: dict,
        output_summary: dict,
        duration_ms: int = 0,
        error_message: str | None = None,
        aggregate_output_keys: tuple[str, ...] = (),
    ) -> None:
        existing = self._stage_index.get(name)
        if existing is None:
            stage = {
                "name": name,
                "status": status,
                "duration_ms": duration_ms,
                "input": input_summary,
                "output": output_summary,
                "error_message": error_message,
            }
            self.payload["stages"].append(stage)
            self._stage_index[name] = stage
            return
        existing["duration_ms"] = int(existing.get("duration_ms") or 0) + duration_ms
        existing["status"] = _merge_stage_status(existing.get("status"), status)
        existing["input"] = _merge_summary(existing.get("input") or {}, input_summary)
        existing["output"] = _merge_summary(
            existing.get("output") or {},
            output_summary,
            aggregate_keys=aggregate_output_keys,
        )
        if error_message:
            existing["error_message"] = error_message

    def finish(self, *, final_hit_count: int) -> None:
        self.payload["hit_count"] = final_hit_count

    def to_dict(self) -> dict:
        return self.payload


def _duration_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _merge_stage_status(current: str | None, new: str) -> str:
    if current == "failed" or new == "failed":
        return "failed"
    if current == "done" or new == "done":
        return "done"
    return new or current or "skipped"


def _merge_summary(existing: dict, new: dict, *, aggregate_keys: tuple[str, ...] = ()) -> dict:
    merged = dict(existing)
    for key, value in new.items():
        if key in aggregate_keys and isinstance(value, int | float):
            merged[key] = merged.get(key, 0) + value
        elif key in merged and merged[key] != value:
            values = merged[key] if isinstance(merged[key], list) else [merged[key]]
            if value not in values:
                values.append(value)
            merged[key] = values
        else:
            merged[key] = value
    return merged


def _validate_mode_allowed(mode: str, strategy: dict) -> None:
    if mode == "vector_only" and not strategy["enable_vector"]:
        raise ValueError("当前知识库未启用向量检索")
    if mode == "keyword_only" and not strategy["enable_keyword"]:
        raise ValueError("当前知识库未启用关键词检索")
    if mode == "hybrid" and not (strategy["enable_vector"] and strategy["enable_keyword"]):
        raise ValueError("混合检索需要同时启用向量检索和关键词检索")


class CompositeKnowledgeRetriever:
    engine = "qdrant+paradedb_bm25"
    vector_engine = "qdrant"
    keyword_engine = "paradedb_bm25"

    def __init__(self, service: KnowledgeSearchService) -> None:
        self.service = service

    def search_kb(
        self,
        query: str,
        *,
        kb,
        config: RetrievalConfigSchema,
        over_retrieval_limit: int,
        mode: str,
        diagnostics: _DiagnosticsBuilder,
        knowledge_ids: list[str] | None,
    ) -> list[RetrievalHit]:
        return self.service._search_kb_with_diagnostics(
            query,
            kb=kb,
            config=config,
            over_retrieval_limit=over_retrieval_limit,
            mode=mode,
            diagnostics=diagnostics,
            knowledge_ids=knowledge_ids,
        )


def _over_retrieval_limit(config: RetrievalConfigSchema, *, scope_count: int) -> int:
    per_scope = max(config.rerank_top_k * 5, 50)
    return min(per_scope * max(scope_count, 1), 500)


_STOPWORDS = {
    "的",
    "是",
    "在",
    "了",
    "和",
    "与",
    "或",
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "how",
    "why",
    "when",
    "where",
    "which",
    "who",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "about",
}
_QUESTION_PREFIX = re.compile(
    r"^(什么是|什么|如何|怎么|怎样|为什么|为何|哪个|哪些|谁|何时|何地|请问|帮我|我想知道|我想了解)"
)
_DELIMITERS = re.compile(r"[,，;；、。！？!?\s]+")
_QUOTED_PHRASE = re.compile(r"[\"'“”‘’「」『』]([^\"'“”‘’「」『』]+)[\"'“”‘’「」『』]")
_SPACED_PHRASE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+(?:\s+[\u4e00-\u9fffA-Za-z0-9]+)+")


def _expand_query_variants(query: str, *, limit: int = 5) -> list[str]:
    normalized = (query or "").strip()
    if not normalized:
        return []
    seen = {normalized.lower()}
    variants: list[str] = []

    def add(value: str) -> None:
        item = value.strip()
        if len(item) < 3:
            return
        key = item.lower()
        if key in seen:
            return
        seen.add(key)
        variants.append(item)

    keywords = [term for term in tokenize_query(normalized) if term.lower() not in _STOPWORDS and len(term) > 1]
    if len(keywords) >= 2:
        add(" ".join(keywords))
    for match in _QUOTED_PHRASE.findall(normalized):
        add(match)
    for match in _SPACED_PHRASE.findall(normalized):
        add(match)
    for segment in _DELIMITERS.split(normalized):
        if len(segment.strip()) > 5:
            add(segment)
    without_question_words = _QUESTION_PREFIX.sub("", normalized).strip()
    if without_question_words != normalized:
        add(without_question_words)
    return variants[:limit]


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
