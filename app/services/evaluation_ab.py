from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.evaluation import EvaluationRepository
from app.services.evaluation import DEFAULT_EVALUATION_METRICS, EvaluationService
from app.services.knowledge_search import KnowledgeSearchService


@dataclass(frozen=True)
class EvaluationVariant:
    name: str
    top_k: int = 5
    enable_rerank: bool = False


class EvaluationABService:
    def __init__(self, db: Session, settings: Settings, *, embedder=None, vector_store=None, reranker=None) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker
        self.repo = EvaluationRepository(db)

    def run_report(
        self,
        *,
        knowledge_base_id: str,
        testset_id: str,
        variants: list[EvaluationVariant],
        tag: str | None = None,
        execute_evaluation: bool = False,
        retrieval_limit: int = 10,
        precision_at: int = 5,
    ) -> dict:
        testset = self.repo.get_testset(testset_id, self.settings.default_tenant_id)
        if testset is None:
            raise LookupError("黄金测试集不存在。")
        if testset.knowledge_base_id != knowledge_base_id:
            raise ValueError("黄金测试集不属于当前知识库。")
        items = self.repo.list_testset_items(testset.id, self.settings.default_tenant_id)
        if not items:
            raise ValueError("黄金测试集没有可用题目。")

        started_at = time.perf_counter()
        rows = []
        for variant in variants:
            variant_started = time.perf_counter()
            retrieval_metrics = self._retrieval_metrics(
                knowledge_base_id=knowledge_base_id,
                items=items,
                top_k=variant.top_k,
                enable_rerank=variant.enable_rerank,
                retrieval_limit=retrieval_limit,
                precision_at=precision_at,
            )
            run_payload = self._execute_evaluation(
                knowledge_base_id=knowledge_base_id,
                testset_id=testset_id,
                testset_size=len(items),
                variant=variant,
            ) if execute_evaluation else {}
            rows.append(
                {
                    "variant": variant.name,
                    "top_k": variant.top_k,
                    "enable_rerank": variant.enable_rerank,
                    "run_id": run_payload.get("run_id"),
                    "overall": run_payload.get("overall"),
                    "metrics": run_payload.get("metrics") or _empty_metrics(),
                    **retrieval_metrics,
                    "failed_count": run_payload.get("failed_count", 0),
                    "duration_ms": int((time.perf_counter() - variant_started) * 1000),
                }
            )
        return {
            "knowledge_base_id": knowledge_base_id,
            "testset_id": testset_id,
            "tag": tag,
            "execute_evaluation": execute_evaluation,
            "retrieval_limit": retrieval_limit,
            "precision_at": precision_at,
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "variants": rows,
        }

    def write_report(self, report: dict, output_path: str | Path) -> None:
        Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _retrieval_metrics(
        self,
        *,
        knowledge_base_id: str,
        items,
        top_k: int,
        enable_rerank: bool,
        retrieval_limit: int,
        precision_at: int,
    ) -> dict:
        search = KnowledgeSearchService(
            self.db,
            self.settings,
            self.embedder,
            self.vector_store,
            reranker=self.reranker,
        )
        recall_values: list[float] = []
        precision_values: list[float] = []
        misses: list[dict] = []
        search_limit = max(retrieval_limit, precision_at, top_k)
        for item in items:
            expected = {str(value) for value in (item.expected_chunk_ids or [])}
            if not expected:
                continue
            result = search.search_with_diagnostics(
                knowledge_base_id=knowledge_base_id,
                query=item.question,
                top_k=search_limit,
                enable_rerank=enable_rerank,
            )
            top_recall_ids = _hit_ids(result.hits[:retrieval_limit])
            top_precision_ids = _hit_ids(result.hits[:precision_at])
            recall = len(expected & top_recall_ids) / len(expected)
            # This is expected-source hit@k, normalized to 0/1 for single-source legal questions.
            precision = 1.0 if expected & top_precision_ids else 0.0
            recall_values.append(recall)
            precision_values.append(precision)
            if recall < 1:
                misses.append(
                    {
                        "sample_index": item.sample_index,
                        "question": item.question,
                        "expected_chunk_ids": sorted(expected),
                        "retrieved_chunk_ids": sorted(top_recall_ids),
                    }
                )
        return {
            "recall_at_10": round(sum(recall_values) / len(recall_values), 4) if recall_values else 0.0,
            "precision_at_5": round(sum(precision_values) / len(precision_values), 4) if precision_values else 0.0,
            "miss_count": len(misses),
            "misses": misses[:20],
        }

    def _execute_evaluation(
        self,
        *,
        knowledge_base_id: str,
        testset_id: str,
        testset_size: int,
        variant: EvaluationVariant,
    ) -> dict:
        service = EvaluationService(self.db, self.settings, embedder=self.embedder, vector_store=self.vector_store)
        run = service.create_run(
            knowledge_base_id=knowledge_base_id,
            testset_id=testset_id,
            testset_size=testset_size,
            top_k=variant.top_k,
            enable_rerank=variant.enable_rerank,
        )
        completed = service.run_evaluation(run.id)
        metrics_summary = completed.metrics_summary or {}
        return {
            "run_id": completed.id,
            "overall": metrics_summary.get("overall_score"),
            "metrics": {
                key: ((metrics_summary.get("metrics") or {}).get(key) or {}).get("average")
                for key in DEFAULT_EVALUATION_METRICS
            },
            "failed_count": completed.failed_sample_count,
        }


def parse_variant(value: str) -> EvaluationVariant:
    name, _, raw_options = value.partition(":")
    if not name:
        raise ValueError("variant 名称不能为空")
    options: dict[str, str] = {}
    for part in raw_options.split(","):
        if not part:
            continue
        key, _, option_value = part.partition("=")
        if not key or not option_value:
            raise ValueError(f"无效 variant 配置：{part}")
        options[key.strip()] = option_value.strip()
    return EvaluationVariant(
        name=name.strip(),
        top_k=int(options.get("top_k", 5)),
        enable_rerank=_bool_option(options.get("rerank") or options.get("enable_rerank") or "false"),
    )


def _bool_option(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y", "on", "重排"}


def _hit_ids(hits) -> set[str]:
    ids: set[str] = set()
    for hit in hits:
        for value in (hit.chunk_id, hit.context_chunk_id, hit.parent_chunk_id):
            if value:
                ids.add(str(value))
    return ids


def _empty_metrics() -> dict:
    return {key: None for key in DEFAULT_EVALUATION_METRICS}
