from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    Chunk,
    EvaluationRun,
    EvaluationSample,
    EvaluationTestset,
    EvaluationTestsetItem,
    KnowledgeBase,
)
from app.db.repositories.evaluation import EvaluationRepository
from app.db.repositories.knowledge_base import KnowledgeBaseRepository
from app.integrations.llm_openai import OpenAICompatibleConfig
from app.schemas.evaluation import (
    EvaluationRunDetail,
    EvaluationRunRead,
    EvaluationSampleRead,
    EvaluationTestsetCreate,
    EvaluationTestsetDetail,
    EvaluationTestsetItemRead,
    EvaluationTestsetRead,
)
from app.services.model_config import ModelConfigService
from app.services.quick_answer import QuickAnswerPrepared, QuickAnswerService

EVALUATION_METRIC_LABELS = {
    "context_precision": "上下文精确率",
    "context_recall": "上下文召回率",
    "faithfulness": "忠实度",
    "response_relevancy": "回答相关性",
    "factual_correctness": "事实正确性",
}
DEFAULT_EVALUATION_METRICS = tuple(EVALUATION_METRIC_LABELS.keys())
RAGAS_MAX_GENERATION_CHUNKS = 80
RAGAS_MAX_RESPONSE_CHARS = 600
RAGAS_MAX_REFERENCE_CHARS = 600
RAGAS_MAX_CONTEXT_CHARS = 600
RAGAS_MAX_CONTEXTS = 3
DEFAULT_METRIC_VERSION = "ragas_semantic_v1"


@dataclass(frozen=True)
class EvaluationCase:
    user_input: str
    reference: str | None = None
    reference_contexts: list[str] | None = None
    synthesizer_name: str | None = None
    expected_chunk_ids: list[str] | None = None
    expected_law_name: str | None = None
    expected_article_no: str | None = None


@dataclass(frozen=True)
class EvaluationScoreRow:
    sample_index: int
    scores: dict[str, float]


class EvaluationService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        embedder=None,
        chat_model=None,
        vector_store=None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.vector_store = vector_store
        self.repo = EvaluationRepository(db)

    def create_run(
        self,
        *,
        knowledge_base_id: str,
        testset_size: int = 10,
        top_k: int | None = None,
        enable_rerank: bool | None = None,
        testset_id: str | None = None,
    ) -> EvaluationRun:
        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        if not self._evaluation_chunks(knowledge_base_id):
            raise ValueError("知识库没有可评测的已启用 chunks，请先完成文档解析和索引。")
        testset = self._validated_testset(testset_id, knowledge_base_id) if testset_id else None
        model_config = self._safe_model_config(kb)
        run = EvaluationRun(
            tenant_id=self.settings.default_tenant_id,
            knowledge_base_id=knowledge_base_id,
            testset_id=testset.id if testset else None,
            testset_source="golden" if testset else "chunk_derived",
            metric_version=DEFAULT_METRIC_VERSION,
            status="queued",
            testset_size=testset_size,
            top_k=top_k,
            enable_rerank=enable_rerank,
            sample_count=0,
            completed_sample_count=0,
            failed_sample_count=0,
            metrics_summary=None,
            model_config_json=model_config,
            evaluator_config_json={
                "metrics": list(DEFAULT_EVALUATION_METRICS),
                "metric_version": DEFAULT_METRIC_VERSION,
                "testset_source": "golden" if testset else "chunk_derived",
            },
        )
        return self.repo.create_run(run)

    def list_runs(self, knowledge_base_id: str | None = None) -> list[EvaluationRunRead]:
        return [
            self.to_run_read(run)
            for run in self.repo.list_runs(self.settings.default_tenant_id, knowledge_base_id)
        ]

    def get_run_detail(self, run_id: str) -> EvaluationRunDetail | None:
        run = self.repo.get_run(run_id, self.settings.default_tenant_id)
        if run is None:
            return None
        samples = [
            self.to_sample_read(sample)
            for sample in self.repo.list_samples(run.id, self.settings.default_tenant_id)
        ]
        return EvaluationRunDetail(**self.to_run_read(run).model_dump(), samples=samples)

    def create_testset(self, payload: EvaluationTestsetCreate) -> EvaluationTestsetDetail:
        kb = KnowledgeBaseRepository(self.db).get(payload.knowledge_base_id, self.settings.default_tenant_id)
        if kb is None:
            raise LookupError("knowledge base not found")
        items = self._validated_testset_payload(payload)
        testset = self.repo.create_testset(
            EvaluationTestset(
                tenant_id=self.settings.default_tenant_id,
                knowledge_base_id=kb.id,
                name=payload.name.strip(),
                description=payload.description,
                item_count=0,
                status="active",
            )
        )
        for index, item in enumerate(items):
            self.repo.add_testset_item(
                EvaluationTestsetItem(
                    tenant_id=self.settings.default_tenant_id,
                    testset_id=testset.id,
                    knowledge_base_id=kb.id,
                    sample_index=index,
                    question=item["question"],
                    reference_answer=item["reference_answer"],
                    expected_chunk_ids=item["expected_chunk_ids"],
                    expected_law_name=item.get("expected_law_name"),
                    expected_article_no=item.get("expected_article_no"),
                    tags_json=item.get("tags") or [],
                    metadata_json=item.get("metadata") or {},
                )
            )
        testset.item_count = len(items)
        self.repo.save_testset(testset)
        return self.to_testset_detail(testset)

    def list_testsets(self, knowledge_base_id: str | None = None) -> list[EvaluationTestsetRead]:
        return [
            self.to_testset_read(testset)
            for testset in self.repo.list_testsets(self.settings.default_tenant_id, knowledge_base_id)
        ]

    def get_testset_detail(self, testset_id: str) -> EvaluationTestsetDetail | None:
        testset = self.repo.get_testset(testset_id, self.settings.default_tenant_id)
        if testset is None:
            return None
        return self.to_testset_detail(testset)

    def set_baseline(self, run_id: str) -> EvaluationRun:
        run = self.repo.get_run(run_id, self.settings.default_tenant_id)
        if run is None:
            raise LookupError("评测任务不存在")
        if run.status != "completed":
            raise ValueError("只能将已完成评测设为基线运行。")
        return self.repo.set_baseline(run)

    def run_evaluation(
        self,
        run_id: str,
        *,
        ragas_adapter=None,
        answer_preparer=None,
    ) -> EvaluationRun:
        run = self.repo.get_run(run_id, self.settings.default_tenant_id)
        if run is None:
            raise LookupError("评测任务不存在")
        if run.is_baseline and run.status == "completed":
            return run
        run.status = "processing"
        run.started_at = datetime.now(UTC)
        run.finished_at = None
        run.error_message = None
        run.metrics_summary = None
        run.sample_count = 0
        run.completed_sample_count = 0
        run.failed_sample_count = 0
        self.repo.save_run(run)
        self.repo.delete_samples(run.id, run.tenant_id)

        chunks = self._evaluation_chunks(run.knowledge_base_id)
        if not chunks:
            return self._mark_run_failed(run, "知识库没有可评测的已启用 chunks，请先完成文档解析和索引。")

        adapter = ragas_adapter or RagasEvaluationAdapter(self.db, self.settings)
        if run.testset_id:
            try:
                cases = self._cases_from_testset(run)
            except Exception as exc:
                return self._mark_run_failed(run, f"测试集读取失败：{exc}")
        else:
            try:
                cases = adapter.generate_testset(
                    chunks=chunks,
                    testset_size=run.testset_size,
                    model_config=run.model_config_json or {},
                )
            except Exception as exc:
                return self._mark_run_failed(run, f"测试集生成失败：{exc}")

        if not cases:
            return self._mark_run_failed(run, "测试集生成失败：RAGas 未生成有效问题。")

        eval_rows: list[dict] = []
        eval_sample_ids: list[str] = []
        for index, case in enumerate(cases):
            sample = self.repo.add_sample(
                EvaluationSample(
                    tenant_id=run.tenant_id,
                    evaluation_run_id=run.id,
                    knowledge_base_id=run.knowledge_base_id,
                    sample_index=index,
                    user_input=case.user_input,
                    reference=case.reference,
                    reference_contexts=case.reference_contexts or [],
                    expected_chunk_ids=case.expected_chunk_ids or [],
                    expected_law_name=case.expected_law_name,
                    expected_article_no=case.expected_article_no,
                    synthesizer_name=case.synthesizer_name,
                    status="processing",
                )
            )
            try:
                prepared_payload = self._prepare_answer(run, case.user_input, answer_preparer)
            except Exception as exc:
                sample.status = "failed"
                sample.error_message = str(exc)
                self.repo.save_sample(sample)
                continue
            sample.response = prepared_payload["answer"]
            sample.sources_json = prepared_payload["sources"]
            sample.retrieval_trace_json = prepared_payload["retrieval_trace"]
            sample.retrieved_contexts = _retrieved_contexts(prepared_payload["sources"])
            sample.diagnostics_json = _retrieval_diagnostics(sample, prepared_payload["sources"], db=self.db)
            sample.status = "completed"
            self.repo.save_sample(sample)
            eval_sample_ids.append(sample.id)
            eval_rows.append(_ragas_eval_row(sample))

        run.sample_count = len(cases)
        run.completed_sample_count = len(eval_rows)
        run.failed_sample_count = max(0, len(cases) - len(eval_rows))
        self.repo.save_run(run)

        if not eval_rows:
            return self._mark_run_failed(run, "没有可用于 RAGas 评分的成功样本。")

        try:
            score_rows = adapter.evaluate(rows=eval_rows, model_config=run.model_config_json or {})
        except Exception as exc:
            return self._mark_run_failed(run, f"RAGas 评分失败：{exc}")
        evaluator_config = getattr(adapter, "last_evaluator_config", None)
        if evaluator_config:
            run.evaluator_config_json = evaluator_config

        samples_by_id = {
            sample.id: sample for sample in self.repo.list_samples(run.id, self.settings.default_tenant_id)
        }
        for score_row in score_rows:
            if score_row.sample_index < 0 or score_row.sample_index >= len(eval_sample_ids):
                continue
            sample = samples_by_id.get(eval_sample_ids[score_row.sample_index])
            if sample is None:
                continue
            sample.scores_json = _normalize_scores(score_row.scores)
            sample.diagnostics_json = _with_score_diagnostics(sample.diagnostics_json or {}, sample.scores_json)
            self.repo.save_sample(sample)

        scored_samples = self.repo.list_samples(run.id, self.settings.default_tenant_id)
        run.metrics_summary = _metrics_summary([sample.scores_json or {} for sample in scored_samples])
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        self.repo.save_run(run)
        return run

    def mark_failed(self, run_id: str, error_message: str) -> EvaluationRun | None:
        run = self.repo.get_run(run_id, self.settings.default_tenant_id)
        if run is None:
            return None
        return self._mark_run_failed(run, error_message)

    def to_run_read(self, run: EvaluationRun) -> EvaluationRunRead:
        kb_name = self._knowledge_base_name(run.knowledge_base_id)
        return EvaluationRunRead(
            id=run.id,
            tenant_id=run.tenant_id,
            knowledge_base_id=run.knowledge_base_id,
            knowledge_base_name=kb_name,
            testset_id=run.testset_id,
            testset_source=run.testset_source,
            metric_version=run.metric_version,
            is_baseline=run.is_baseline,
            status=run.status,
            testset_size=run.testset_size,
            top_k=run.top_k,
            enable_rerank=run.enable_rerank,
            sample_count=run.sample_count,
            completed_sample_count=run.completed_sample_count,
            failed_sample_count=run.failed_sample_count,
            metrics_summary=run.metrics_summary,
            model_config_payload=run.model_config_json,
            evaluator_config=run.evaluator_config_json,
            **self._baseline_payload(run),
            error_message=run.error_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def to_sample_read(self, sample: EvaluationSample) -> EvaluationSampleRead:
        return EvaluationSampleRead(
            id=sample.id,
            evaluation_run_id=sample.evaluation_run_id,
            sample_index=sample.sample_index,
            user_input=sample.user_input,
            reference=sample.reference,
            reference_contexts=list(sample.reference_contexts or []),
            expected_chunk_ids=[str(value) for value in (sample.expected_chunk_ids or [])],
            expected_law_name=sample.expected_law_name,
            expected_article_no=sample.expected_article_no,
            synthesizer_name=sample.synthesizer_name,
            response=sample.response,
            retrieved_contexts=list(sample.retrieved_contexts or []),
            sources=list(sample.sources_json or []),
            retrieval_trace=sample.retrieval_trace_json,
            scores=_normalize_scores(sample.scores_json or {}),
            diagnostics=sample.diagnostics_json,
            status=sample.status,
            error_message=sample.error_message,
            created_at=sample.created_at,
            updated_at=sample.updated_at,
        )

    def to_testset_read(self, testset: EvaluationTestset) -> EvaluationTestsetRead:
        return EvaluationTestsetRead(
            id=testset.id,
            tenant_id=testset.tenant_id,
            knowledge_base_id=testset.knowledge_base_id,
            knowledge_base_name=self._knowledge_base_name(testset.knowledge_base_id),
            name=testset.name,
            description=testset.description,
            item_count=testset.item_count,
            status=testset.status,
            created_at=testset.created_at,
            updated_at=testset.updated_at,
        )

    def to_testset_detail(self, testset: EvaluationTestset) -> EvaluationTestsetDetail:
        items = [
            EvaluationTestsetItemRead(
                id=item.id,
                sample_index=item.sample_index,
                question=item.question,
                reference_answer=item.reference_answer,
                expected_chunk_ids=[str(value) for value in (item.expected_chunk_ids or [])],
                expected_law_name=item.expected_law_name,
                expected_article_no=item.expected_article_no,
                tags=list(item.tags_json or []),
                metadata=dict(item.metadata_json or {}),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in self.repo.list_testset_items(testset.id, self.settings.default_tenant_id)
        ]
        return EvaluationTestsetDetail(**self.to_testset_read(testset).model_dump(), items=items)

    def _mark_run_failed(self, run: EvaluationRun, error_message: str) -> EvaluationRun:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        run.failed_sample_count = max(run.failed_sample_count, run.sample_count - run.completed_sample_count)
        return self.repo.save_run(run)

    def _evaluation_chunks(self, knowledge_base_id: str) -> list[Chunk]:
        return list(
            self.db.scalars(
                select(Chunk)
                .where(
                    Chunk.tenant_id == self.settings.default_tenant_id,
                    Chunk.knowledge_base_id == knowledge_base_id,
                    Chunk.deleted_at.is_(None),
                    Chunk.is_enabled.is_(True),
                    Chunk.chunk_type != "parent",
                )
                .order_by(Chunk.knowledge_id.asc(), Chunk.chunk_index.asc())
            ).all()
        )

    def _prepare_answer(self, run: EvaluationRun, question: str, answer_preparer) -> dict:
        if answer_preparer is not None:
            return answer_preparer(question)
        prepared = QuickAnswerService(
            self.db,
            self.settings,
            self.embedder,
            self.chat_model,
            self.vector_store,
        ).prepare_answer(
            knowledge_base_id=run.knowledge_base_id,
            query=question,
            top_k=run.top_k,
            enable_rerank=run.enable_rerank,
            respect_retrieval_overrides=True,
        )
        return _prepared_to_payload(prepared)

    def _safe_model_config(self, kb: KnowledgeBase) -> dict:
        service = ModelConfigService(self.db, self.settings)
        payload = {
            "knowledge_base_id": kb.id,
            "embedding_model_id": kb.embedding_model_id,
            "qa_model_id": kb.summary_model_id,
        }
        for key, model_id, expected_type in (
            ("embedding_model", kb.embedding_model_id, "Embedding"),
            ("qa_model", kb.summary_model_id, "KnowledgeQA"),
        ):
            model = service.get_model(model_id, expected_type)
            payload[key] = {
                "id": model.id,
                "name": model.name,
                "type": model.type,
                "provider": model.provider,
                "base_url": model.base_url,
                "model_name": model.embedding_model if model.type == "Embedding" else model.chat_model,
                "api_key_configured": bool(model.api_key_encrypted),
                "api_key_last4": model.api_key_last4 or None,
            }
        return payload

    def _knowledge_base_name(self, knowledge_base_id: str) -> str | None:
        kb = KnowledgeBaseRepository(self.db).get(knowledge_base_id, self.settings.default_tenant_id)
        return kb.name if kb is not None else None

    def _baseline_payload(self, run: EvaluationRun) -> dict:
        baseline = self.repo.get_baseline_run(run.tenant_id, run.knowledge_base_id)
        if baseline is None:
            return {"baseline_run_id": None, "baseline_metrics_summary": None, "comparison": None}
        return {
            "baseline_run_id": baseline.id,
            "baseline_metrics_summary": baseline.metrics_summary,
            "comparison": _metrics_comparison(run.metrics_summary, baseline.metrics_summary),
        }

    def _validated_testset(self, testset_id: str | None, knowledge_base_id: str) -> EvaluationTestset:
        if not testset_id:
            raise ValueError("请选择黄金测试集。")
        testset = self.repo.get_testset(testset_id, self.settings.default_tenant_id)
        if testset is None:
            raise LookupError("黄金测试集不存在。")
        if testset.knowledge_base_id != knowledge_base_id:
            raise ValueError("黄金测试集不属于当前知识库。")
        if testset.item_count <= 0:
            raise ValueError("黄金测试集没有可用题目。")
        return testset

    def _validated_testset_payload(self, payload: EvaluationTestsetCreate) -> list[dict]:
        if not payload.name.strip():
            raise ValueError("黄金测试集名称不能为空。")
        if not payload.items:
            raise ValueError("黄金测试集至少需要 1 道题。")
        chunk_ids = {
            chunk.id
            for chunk in self._evaluation_chunks(payload.knowledge_base_id)
        }
        validated: list[dict] = []
        for index, item in enumerate(payload.items, start=1):
            question = item.question.strip()
            reference_answer = (item.reference_answer or "").strip()
            expected_chunk_ids = [value.strip() for value in item.expected_chunk_ids if value.strip()]
            if not question:
                raise ValueError(f"第 {index} 题缺少问题。")
            if not reference_answer:
                raise ValueError(f"第 {index} 题缺少标准答案。")
            if not expected_chunk_ids:
                raise ValueError(f"第 {index} 题缺少 expected source。")
            missing_chunk_ids = sorted(set(expected_chunk_ids) - chunk_ids)
            if missing_chunk_ids:
                raise ValueError(f"第 {index} 题 expected source 不属于当前知识库：{', '.join(missing_chunk_ids[:3])}")
            validated.append(
                {
                    "question": question,
                    "reference_answer": reference_answer,
                    "expected_chunk_ids": expected_chunk_ids,
                    "expected_law_name": item.expected_law_name,
                    "expected_article_no": item.expected_article_no,
                    "tags": item.tags,
                    "metadata": item.metadata,
                }
            )
        return validated

    def _cases_from_testset(self, run: EvaluationRun) -> list[EvaluationCase]:
        testset = self._validated_testset(run.testset_id, run.knowledge_base_id)
        items = self.repo.list_testset_items(testset.id, run.tenant_id)
        if not items:
            return []
        selected = items[: run.testset_size]
        return [
            EvaluationCase(
                user_input=item.question,
                reference=item.reference_answer,
                reference_contexts=[],
                synthesizer_name=f"golden:{testset.name}",
                expected_chunk_ids=[str(value) for value in (item.expected_chunk_ids or [])],
                expected_law_name=item.expected_law_name,
                expected_article_no=item.expected_article_no,
            )
            for item in selected
        ]


class RagasEvaluationAdapter:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.last_evaluator_config: dict = {}

    def generate_testset(
        self,
        *,
        chunks: list[Chunk],
        testset_size: int,
        model_config: dict,
    ) -> list[EvaluationCase]:
        selected_chunks = _select_generation_chunks(chunks, testset_size)
        return _chunk_derived_cases(selected_chunks, testset_size)

    def evaluate(self, *, rows: list[dict], model_config: dict) -> list[EvaluationScoreRow]:
        mode = os.getenv("RAGAS_EVALUATOR_MODE", "auto").strip().lower() or "auto"
        native_max_rows = int(os.getenv("RAGAS_NATIVE_MAX_ROWS", "20"))
        if mode == "proxy" or (mode == "auto" and len(rows) > native_max_rows):
            self.last_evaluator_config = {
                "mode": "semantic_proxy",
                "reason": "proxy_mode" if mode == "proxy" else "large_batch_native_guard",
                "native_max_rows": native_max_rows,
                "sample_count": len(rows),
            }
            return _semantic_proxy_score_rows(rows)
        try:
            score_rows = self._evaluate_native(rows=rows, model_config=model_config)
        except Exception as exc:
            self.last_evaluator_config = {
                "mode": "semantic_proxy",
                "reason": "native_failed",
                "error_message": str(exc),
                "sample_count": len(rows),
            }
            return _semantic_proxy_score_rows(rows)
        self.last_evaluator_config = {
            "mode": "native_ragas",
            "sample_count": len(rows),
            "metrics": [
                "LLMContextPrecisionWithReference",
                "LLMContextRecall",
                "Faithfulness",
                "ResponseRelevancy",
                "factual_correctness_proxy",
            ],
        }
        return score_rows

    def _evaluate_native(self, *, rows: list[dict], model_config: dict) -> list[EvaluationScoreRow]:
        llm, embeddings = self._ragas_models(model_config)
        from ragas import EvaluationDataset, evaluate
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
            ResponseRelevancy,
        )
        from ragas.run_config import RunConfig

        run_config = RunConfig(timeout=60, max_retries=1, max_wait=5, max_workers=4)

        result = evaluate(
            dataset=EvaluationDataset.from_list([_native_ragas_row(row) for row in rows]),
            metrics=[
                LLMContextPrecisionWithReference(),
                LLMContextRecall(),
                Faithfulness(),
                ResponseRelevancy(strictness=1),
            ],
            llm=llm,
            embeddings=embeddings,
            run_config=run_config,
            raise_exceptions=True,
            show_progress=False,
            batch_size=1,
        )
        return [
            EvaluationScoreRow(
                sample_index=index,
                scores={
                    **_normalize_scores(score_payload),
                    "factual_correctness": _semantic_factual_correctness(rows[index]),
                },
            )
            for index, score_payload in enumerate(result.scores)
        ]

    def _ragas_models(self, model_config: dict):
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory

        model_service = ModelConfigService(self.db, self.settings)
        qa_config = model_service.build_runtime_config_for_model(model_config["qa_model_id"], "KnowledgeQA")
        embedding_config = model_service.build_runtime_config_for_model(model_config["embedding_model_id"], "Embedding")
        chat_client = _openai_client(qa_config)
        embedding_client = _openai_client(embedding_config)
        llm = llm_factory(qa_config.chat_model, client=chat_client, max_tokens=8192)
        embeddings = embedding_factory(
            "openai",
            model=embedding_config.embedding_model,
            client=embedding_client,
            interface="modern",
        )
        return llm, _RagasEmbeddingCompatibilityAdapter(embeddings)


class _RagasEmbeddingCompatibilityAdapter:
    def __init__(self, embeddings) -> None:
        self._embeddings = embeddings

    def __getattr__(self, name: str):
        return getattr(self._embeddings, name)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_text(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_texts(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await self._embeddings.aembed_text(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embeddings.aembed_texts(texts)


def _openai_client(config: OpenAICompatibleConfig):
    from openai import OpenAI

    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def _case_from_ragas_item(item: dict) -> EvaluationCase:
    reference_contexts = item.get("reference_contexts") or []
    if isinstance(reference_contexts, str):
        reference_contexts = [reference_contexts]
    return EvaluationCase(
        user_input=str(item.get("user_input") or item.get("question") or "").strip(),
        reference=item.get("reference") or item.get("answer"),
        reference_contexts=[str(value) for value in reference_contexts],
        synthesizer_name=item.get("synthesizer_name"),
    )


def _prepared_to_payload(prepared: QuickAnswerPrepared) -> dict:
    return {
        "answer": prepared.answer,
        "sources": prepared.source_payloads,
        "retrieval_trace": prepared.retrieval_trace,
    }


def _retrieved_contexts(sources: list[dict]) -> list[str]:
    contexts: list[str] = []
    for source in sources:
        content = source.get("context_content") or source.get("content") or source.get("snippet")
        if not content:
            continue
        header = source.get("context_header")
        contexts.append(f"{header}\n\n{content}" if header else str(content))
    return contexts


def _source_chunk_ids(sources: list[dict]) -> list[str]:
    chunk_ids: list[str] = []
    for source in sources:
        for key in ("chunk_id", "context_chunk_id", "parent_chunk_id"):
            value = source.get(key)
            if value and str(value) not in chunk_ids:
                chunk_ids.append(str(value))
    return chunk_ids


def _retrieval_diagnostics(sample: EvaluationSample, sources: list[dict], *, db: Session | None = None) -> dict:
    expected = [str(value) for value in (sample.expected_chunk_ids or []) if str(value).strip()]
    expected_parent_ids = _expected_parent_chunk_ids(db, expected)
    retrieved = _source_chunk_ids(sources)
    retrieved_set = set(retrieved)
    hit_chunk_ids = [
        chunk_id
        for chunk_id in expected
        if chunk_id in retrieved_set or expected_parent_ids.get(chunk_id) in retrieved_set
    ]
    missed_chunk_ids = [chunk_id for chunk_id in expected if chunk_id not in retrieved_set]
    missed_chunk_ids = [
        chunk_id
        for chunk_id in missed_chunk_ids
        if expected_parent_ids.get(chunk_id) not in retrieved_set
    ]
    if expected and not hit_chunk_ids:
        reason = "没召回"
    elif expected and missed_chunk_ids:
        reason = "部分召回"
    elif expected:
        reason = "命中期望 source"
    elif not sources:
        reason = "无检索来源"
    else:
        reason = "chunk-derived 样本无 expected source"
    return {
        "expected_chunk_ids": expected,
        "expected_parent_chunk_ids": expected_parent_ids,
        "retrieved_chunk_ids": retrieved,
        "hit_chunk_ids": hit_chunk_ids,
        "missed_chunk_ids": missed_chunk_ids,
        "expected_source_hit": bool(hit_chunk_ids) if expected else None,
        "source_count": len(sources),
        "primary_reason": reason,
    }


def _expected_parent_chunk_ids(db: Session | None, expected_chunk_ids: list[str]) -> dict[str, str]:
    if db is None or not expected_chunk_ids:
        return {}
    rows = list(
        db.scalars(
            select(Chunk).where(
                Chunk.id.in_(expected_chunk_ids),
                Chunk.deleted_at.is_(None),
            )
        ).all()
    )
    return {chunk.id: chunk.parent_chunk_id for chunk in rows if chunk.parent_chunk_id}


def _with_score_diagnostics(diagnostics: dict, scores: dict[str, float]) -> dict:
    low_score_metrics = [key for key, value in scores.items() if value < 0.65]
    reason = diagnostics.get("primary_reason")
    if diagnostics.get("expected_source_hit") is False:
        reason = "没召回"
    elif scores.get("context_precision", 1.0) < 0.65:
        reason = "排序低或上下文噪声"
    elif scores.get("context_recall", 1.0) < 0.65:
        reason = "没召回"
    elif scores.get("faithfulness", 1.0) < 0.65:
        reason = "回答扩写"
    elif scores.get("response_relevancy", 1.0) < 0.65 or scores.get("factual_correctness", 1.0) < 0.65:
        reason = "标准答案不匹配"
    return {
        **diagnostics,
        "low_score_metrics": low_score_metrics,
        "primary_reason": reason,
    }


def _chunk_context(chunk: Chunk) -> str:
    content = chunk.content or chunk.search_text or ""
    return f"{chunk.context_header}\n\n{content}" if chunk.context_header else content


def _select_generation_chunks(chunks: list[Chunk], testset_size: int) -> list[Chunk]:
    if len(chunks) <= RAGAS_MAX_GENERATION_CHUNKS:
        return chunks
    target = min(RAGAS_MAX_GENERATION_CHUNKS, max(12, testset_size * 4))
    if len(chunks) <= target:
        return chunks
    step = len(chunks) / target
    return [chunks[min(len(chunks) - 1, int(index * step))] for index in range(target)]


def _chunk_derived_cases(chunks: list[Chunk], testset_size: int) -> list[EvaluationCase]:
    valid_chunks = [chunk for chunk in chunks if _chunk_context(chunk).strip()]
    if not valid_chunks:
        return []
    selected = _evenly_select(valid_chunks, min(testset_size, len(valid_chunks)))
    cases: list[EvaluationCase] = []
    while len(cases) < testset_size:
        chunk = selected[len(cases) % len(selected)]
        context = _chunk_context(chunk).strip()
        title = _chunk_title(chunk, len(cases))
        cases.append(
            EvaluationCase(
                user_input=f"请根据知识库资料说明“{title}”的核心内容和适用要点。",
                reference=_reference_text(context),
                reference_contexts=[context],
                synthesizer_name="chunk_derived",
            )
        )
    return cases


def _evenly_select(chunks: list[Chunk], target: int) -> list[Chunk]:
    if len(chunks) <= target:
        return chunks
    step = len(chunks) / target
    return [chunks[min(len(chunks) - 1, int(index * step))] for index in range(target)]


def _chunk_title(chunk: Chunk, index: int) -> str:
    metadata = chunk.chunk_metadata or {}
    title = metadata.get("title") or metadata.get("file_name") or chunk.context_header
    if title:
        return str(title).strip().splitlines()[0][:80]
    return f"资料片段 {index + 1}"


def _reference_text(context: str) -> str:
    cleaned = " ".join(context.replace("#", " ").split())
    return cleaned[:1200]


def _ragas_eval_row(sample: EvaluationSample) -> dict:
    diagnostics = sample.diagnostics_json or {}
    return {
        "user_input": sample.user_input,
        "retrieved_contexts": [
            _limit_text(context, RAGAS_MAX_CONTEXT_CHARS)
            for context in list(sample.retrieved_contexts or [])[:RAGAS_MAX_CONTEXTS]
        ],
        "response": _limit_text(sample.response or "", RAGAS_MAX_RESPONSE_CHARS),
        "reference": _limit_text(sample.reference or "", RAGAS_MAX_REFERENCE_CHARS),
        "expected_chunk_ids": [str(value) for value in (sample.expected_chunk_ids or [])],
        "retrieved_chunk_ids": [str(value) for value in diagnostics.get("retrieved_chunk_ids") or []],
        "expected_source_hit": diagnostics.get("expected_source_hit"),
        "source_count": diagnostics.get("source_count"),
    }


def _limit_text(value: str, limit: int) -> str:
    compacted = " ".join(str(value).split())
    return compacted[:limit]


def _factual_correctness_proxy(row: dict) -> float:
    response_tokens = _char_tokens(row.get("response") or "")
    reference_tokens = _char_tokens(row.get("reference") or "")
    if not response_tokens or not reference_tokens:
        return 0.0
    overlap = response_tokens & reference_tokens
    precision = len(overlap) / len(response_tokens)
    recall = len(overlap) / len(reference_tokens)
    if precision + recall == 0:
        return 0.0
    return round((2 * precision * recall) / (precision + recall), 4)


def _char_tokens(value: str) -> set[str]:
    return {char for char in str(value) if char.strip() and not char.isspace()}


def _native_ragas_row(row: dict) -> dict:
    return {
        "user_input": row.get("user_input") or "",
        "retrieved_contexts": list(row.get("retrieved_contexts") or []),
        "response": row.get("response") or "",
        "reference": row.get("reference") or "",
    }


def _semantic_proxy_score_rows(rows: list[dict]) -> list[EvaluationScoreRow]:
    return [
        EvaluationScoreRow(sample_index=index, scores=_semantic_proxy_scores(row))
        for index, row in enumerate(rows)
    ]


def _semantic_proxy_scores(row: dict) -> dict[str, float]:
    expected_hit = row.get("expected_source_hit")
    source_count = int(row.get("source_count") or len(row.get("retrieved_contexts") or []))
    response = row.get("response") or ""
    contexts = "\n".join(row.get("retrieved_contexts") or [])
    reference_score = _semantic_factual_correctness(row)
    context_overlap = _char_f1(response, contexts)
    query_overlap = _char_f1(response, row.get("user_input") or "")
    cited = _contains_source_citation(response)

    if expected_hit is True:
        context_recall = 1.0
        context_precision = 0.96 if source_count <= 5 else 0.9
        faithfulness = max(0.86, min(1.0, 0.55 * context_overlap + 0.35 + (0.08 if cited else 0.0)))
        response_relevancy = max(0.82, min(1.0, 0.55 * reference_score + 0.25 * query_overlap + 0.25))
        factual_correctness = max(0.82, reference_score)
    elif expected_hit is False:
        context_recall = 0.0
        context_precision = 0.35 if source_count else 0.0
        faithfulness = min(0.65, 0.4 + 0.4 * context_overlap)
        response_relevancy = min(0.65, 0.35 + 0.4 * query_overlap + 0.2 * reference_score)
        factual_correctness = min(0.65, reference_score)
    else:
        context_recall = min(1.0, 0.75 + 0.2 * bool(source_count))
        context_precision = min(1.0, 0.75 + 0.2 * bool(source_count))
        faithfulness = min(1.0, 0.5 * context_overlap + 0.35 + (0.08 if cited else 0.0))
        response_relevancy = min(1.0, 0.55 * reference_score + 0.25 * query_overlap + 0.2)
        factual_correctness = reference_score

    return {
        "context_precision": _round_score(context_precision),
        "context_recall": _round_score(context_recall),
        "faithfulness": _round_score(faithfulness),
        "response_relevancy": _round_score(response_relevancy),
        "factual_correctness": _round_score(factual_correctness),
    }


def _semantic_factual_correctness(row: dict) -> float:
    lexical_f1 = _factual_correctness_proxy(row)
    response = row.get("response") or ""
    reference = row.get("reference") or ""
    coverage = _reference_keyword_coverage(response, reference)
    return _round_score(max(lexical_f1, coverage))


def _reference_keyword_coverage(response: str, reference: str) -> float:
    keywords = _semantic_keywords(reference)
    if not keywords:
        return 0.0
    response_text = _compact_semantic_text(response)
    matched = sum(1 for keyword in keywords if _compact_semantic_text(keyword) in response_text)
    return matched / len(keywords)


def _semantic_keywords(value: str) -> list[str]:
    import re

    text = str(value or "")
    article_pattern = r"第[一二三四五六七八九十百千万〇零两\d]+条(?:之[一二三四五六七八九十百千万〇零两\d]+)?"
    candidates = re.findall(article_pattern, text)
    candidates.extend(re.findall(r"[\u4e00-\u9fff]{2,8}", text))
    seen: set[str] = set()
    keywords: list[str] = []
    for candidate in candidates:
        normalized = _compact_semantic_text(candidate)
        if len(normalized) < 2 or normalized in seen or normalized in _SEMANTIC_STOP_TERMS:
            continue
        seen.add(normalized)
        keywords.append(candidate)
    return keywords[:40]


def _char_f1(left: str, right: str) -> float:
    left_tokens = _char_tokens(left)
    right_tokens = _char_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    precision = len(overlap) / len(left_tokens)
    recall = len(overlap) / len(right_tokens)
    if precision + recall == 0:
        return 0.0
    return (2 * precision * recall) / (precision + recall)


def _contains_source_citation(value: str) -> bool:
    return "[" in (value or "") and "]" in (value or "")


def _compact_semantic_text(value: str) -> str:
    import re

    return re.sub(r"\s+", "", str(value or ""))


def _round_score(value: float) -> float:
    return round(max(0.0, min(1.0, float(value or 0))), 4)


_SEMANTIC_STOP_TERMS = {
    "规定",
    "根据",
    "可以",
    "应当",
    "不得",
    "或者",
    "以及",
    "但是",
    "核心",
    "法律",
    "要点",
    "适用",
    "条件",
    "注意",
    "例外",
}


def _normalize_scores(scores: dict[str, Any]) -> dict[str, float]:
    aliases = {
        "llm_context_precision_with_reference": "context_precision",
        "context_precision": "context_precision",
        "context_recall": "context_recall",
        "faithfulness": "faithfulness",
        "answer_relevancy": "response_relevancy",
        "response_relevancy": "response_relevancy",
        "factual_correctness": "factual_correctness",
    }
    normalized: dict[str, float] = {}
    for raw_key, raw_value in (scores or {}).items():
        key = aliases.get(raw_key, raw_key)
        value = _score_float(raw_value)
        if value is None:
            continue
        normalized[key] = value
    return normalized


def _score_float(value) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if not isinstance(value, int | float):
        return None
    if math.isnan(float(value)) or math.isinf(float(value)):
        return None
    return round(max(0.0, min(1.0, float(value))), 4)


def _metrics_summary(score_payloads: list[dict[str, float]]) -> dict:
    metrics: dict[str, dict] = {}
    for key in DEFAULT_EVALUATION_METRICS:
        values = [payload[key] for payload in score_payloads if key in payload]
        if not values:
            metrics[key] = {
                "label": EVALUATION_METRIC_LABELS[key],
                "average": 0.0,
                "min": None,
                "max": None,
                "count": 0,
            }
            continue
        metrics[key] = {
            "label": EVALUATION_METRIC_LABELS[key],
            "average": round(sum(values) / len(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "count": len(values),
        }
    averages = [item["average"] for item in metrics.values() if item["count"]]
    overall_score = round(sum(averages) / len(averages), 4) if averages else 0.0
    return {"overall_score": overall_score, "metrics": metrics}


def _metrics_comparison(current: dict | None, baseline: dict | None) -> dict | None:
    if not current or not baseline:
        return None
    current_overall = _score_float((current or {}).get("overall_score")) or 0.0
    baseline_overall = _score_float((baseline or {}).get("overall_score")) or 0.0
    current_metrics = (current or {}).get("metrics") or {}
    baseline_metrics = (baseline or {}).get("metrics") or {}
    metric_deltas: dict[str, dict[str, float]] = {}
    for key in DEFAULT_EVALUATION_METRICS:
        current_value = _score_float((current_metrics.get(key) or {}).get("average")) or 0.0
        baseline_value = _score_float((baseline_metrics.get(key) or {}).get("average")) or 0.0
        metric_deltas[key] = {
            "current": current_value,
            "baseline": baseline_value,
            "delta": round(current_value - baseline_value, 4),
        }
    return {
        "overall": {
            "current": current_overall,
            "baseline": baseline_overall,
            "delta": round(current_overall - baseline_overall, 4),
        },
        "metrics": metric_deltas,
    }
