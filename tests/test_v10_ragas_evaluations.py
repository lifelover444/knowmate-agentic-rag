from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge
from app.services.evaluation import (
    EvaluationCase,
    EvaluationScoreRow,
    EvaluationService,
    RagasEvaluationAdapter,
    _retrieval_diagnostics,
)


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "RAGas evaluation KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_completed_document_with_chunks(db_session, kb_id: str, *, chunk_count: int = 3) -> None:
    db_session.add(
        Knowledge(
            id="doc-ragas-eval",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            source_type="file",
            title="RAGas Guide",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    for index in range(chunk_count):
        db_session.add(
            Chunk(
                id=f"chunk-ragas-eval-{index}",
                tenant_id=10000,
                knowledge_base_id=kb_id,
                knowledge_id="doc-ragas-eval",
                content=f"RAGas evaluation chunk {index} explains quick answer quality.",
                search_text=f"ragas evaluation quick answer quality {index}",
                chunk_index=index,
                is_enabled=True,
                start_at=index * 10,
                end_at=index * 10 + 9,
                chunk_type="child",
                context_header="RAGas Guide",
                chunk_metadata={"title": "RAGas Guide", "source_type": "document"},
            )
        )
    db_session.commit()


class FakeRagasAdapter:
    def generate_testset(self, *, chunks, testset_size: int, model_config: dict) -> list[EvaluationCase]:
        return [
            EvaluationCase(
                user_input="What does RAGas measure?",
                reference="RAGas measures RAG answer quality.",
                reference_contexts=["RAGas evaluation chunk 0 explains quick answer quality."],
                synthesizer_name="fake_single_hop",
            ),
            EvaluationCase(
                user_input="broken question",
                reference="This row should keep its failure.",
                reference_contexts=["RAGas evaluation chunk 1 explains quick answer quality."],
                synthesizer_name="fake_single_hop",
            ),
            EvaluationCase(
                user_input="Which workflow is evaluated?",
                reference="Quick answer is evaluated.",
                reference_contexts=["RAGas evaluation chunk 2 explains quick answer quality."],
                synthesizer_name="fake_multi_hop",
            ),
        ][:testset_size]

    def evaluate(self, *, rows, model_config: dict) -> list[EvaluationScoreRow]:
        return [
            EvaluationScoreRow(
                sample_index=index,
                scores={
                    "context_precision": 0.8,
                    "context_recall": 0.7,
                    "faithfulness": 0.9,
                    "response_relevancy": 0.6,
                    "factual_correctness": 0.5,
                },
            )
            for index, _row in enumerate(rows)
        ]


def test_ragas_adapter_auto_uses_semantic_proxy_for_large_batches(client: TestClient, db_session, monkeypatch):
    monkeypatch.delenv("RAGAS_EVALUATOR_MODE", raising=False)
    monkeypatch.setenv("RAGAS_NATIVE_MAX_ROWS", "1")
    row = {
        "user_input": "请说明中华人民共和国行政处罚法第七十六条的法律责任。",
        "retrieved_contexts": ["第七十六条 行政机关违法实施行政处罚的，由上级行政机关责令改正。"],
        "response": "根据第七十六条，行政机关违法实施行政处罚的，由上级行政机关责令改正。[1]",
        "reference": "第七十六条 行政机关违法实施行政处罚的，由上级行政机关责令改正。",
        "expected_source_hit": True,
        "source_count": 1,
    }

    adapter = RagasEvaluationAdapter(db_session, client.app.state.settings)
    scores = adapter.evaluate(rows=[row, row], model_config={})[0].scores

    assert adapter.last_evaluator_config["mode"] == "semantic_proxy"
    assert scores["context_precision"] >= 0.9
    assert scores["context_recall"] == 1.0
    assert scores["faithfulness"] >= 0.85
    assert scores["factual_correctness"] >= 0.8


def test_retrieval_diagnostics_treats_expected_child_parent_as_hit(db_session):
    db_session.add(
        Chunk(
            id="expected-child",
            tenant_id=10000,
            knowledge_base_id="kb-parent-hit",
            knowledge_id="doc-parent-hit",
            content="expected child content",
            search_text="expected child content",
            chunk_index=1,
            is_enabled=True,
            start_at=0,
            end_at=10,
            chunk_type="child",
            parent_chunk_id="selected-parent",
        )
    )
    db_session.commit()
    sample = type("Sample", (), {"expected_chunk_ids": ["expected-child"]})()

    diagnostics = _retrieval_diagnostics(
        sample,
        [{"chunk_id": "other-child", "parent_chunk_id": "selected-parent"}],
        db=db_session,
    )

    assert diagnostics["expected_source_hit"] is True
    assert diagnostics["hit_chunk_ids"] == ["expected-child"]
    assert diagnostics["missed_chunk_ids"] == []


def _answer_preparer(question: str):
    if question == "broken question":
        raise RuntimeError("fake answer failure")
    return {
        "answer": f"answer for {question}",
        "sources": [
            {
                "document_id": "doc-ragas-eval",
                "knowledge_base_id": "kb",
                "chunk_id": "chunk-ragas-eval-0",
                "title": "RAGas Guide",
                "content": "RAGas evaluation chunk 0 explains quick answer quality.",
                "score": 0.98,
            }
        ],
        "retrieval_trace": {"hit_count": 1, "stages": [{"name": "search", "status": "done"}]},
    }


def test_create_evaluation_run_queues_task_and_hides_credentials(client: TestClient, db_session, monkeypatch):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_evaluation_run", enqueued.append)

    response = client.post(
        "/api/v1/evaluations",
        json={"knowledge_base_id": kb_id, "testset_size": 3, "top_k": 4, "enable_rerank": False},
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["knowledge_base_id"] == kb_id
    assert payload["testset_size"] == 3
    assert payload["model_config"]["qa_model"]["api_key_last4"] == "1234"
    assert payload["model_config"]["embedding_model"]["api_key_last4"] == "1234"
    assert "sk-test-1234" not in response.text
    assert "api_key_encrypted" not in response.text
    assert enqueued == [payload["id"]]

    detail_response = client.get(f"/api/v1/evaluations/{payload['id']}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["samples"] == []


def test_create_evaluation_rejects_kb_without_enabled_chunks(client: TestClient):
    kb_id = _create_kb(client)

    response = client.post("/api/v1/evaluations", json={"knowledge_base_id": kb_id, "testset_size": 3})

    assert response.status_code == 400
    assert "知识库没有可评测的已启用 chunks" in response.text


def test_run_evaluation_records_scores_and_failed_samples(client: TestClient, db_session):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)
    service = EvaluationService(db_session, client.app.state.settings)
    run = service.create_run(knowledge_base_id=kb_id, testset_size=3, top_k=3, enable_rerank=False)

    completed = service.run_evaluation(
        run.id,
        ragas_adapter=FakeRagasAdapter(),
        answer_preparer=_answer_preparer,
    )

    assert completed.status == "completed"
    assert completed.completed_sample_count == 2
    assert completed.failed_sample_count == 1
    assert completed.metrics_summary["overall_score"] == 0.7
    assert completed.metrics_summary["metrics"]["faithfulness"]["average"] == 0.9

    detail = service.get_run_detail(run.id)
    assert detail is not None
    assert [sample.status for sample in detail.samples] == ["completed", "failed", "completed"]
    assert detail.samples[1].error_message == "fake answer failure"
    assert detail.samples[0].scores["context_recall"] == 0.7
    assert detail.samples[0].sources[0]["title"] == "RAGas Guide"
    assert detail.samples[0].diagnostics["source_count"] == 1


def test_run_evaluation_marks_generation_failure(client: TestClient, db_session):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)
    service = EvaluationService(db_session, client.app.state.settings)
    run = service.create_run(knowledge_base_id=kb_id, testset_size=3)

    class BrokenRagasAdapter:
        def generate_testset(self, *, chunks, testset_size: int, model_config: dict) -> list[EvaluationCase]:
            raise RuntimeError("synthetic generation unavailable")

    failed = service.run_evaluation(run.id, ragas_adapter=BrokenRagasAdapter())

    assert failed.status == "failed"
    assert "测试集生成失败：synthetic generation unavailable" == failed.error_message


def test_create_evaluation_validates_testset_size(client: TestClient):
    kb_id = _create_kb(client)

    response = client.post("/api/v1/evaluations", json={"knowledge_base_id": kb_id, "testset_size": 2})

    assert response.status_code == 422


def test_baseline_run_is_locked_against_rerun(client: TestClient, db_session):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)
    service = EvaluationService(db_session, client.app.state.settings)
    run = service.create_run(knowledge_base_id=kb_id, testset_size=3, top_k=3, enable_rerank=False)
    completed = service.run_evaluation(
        run.id,
        ragas_adapter=FakeRagasAdapter(),
        answer_preparer=_answer_preparer,
    )

    baseline_response = client.post(f"/api/v1/evaluations/{completed.id}/baseline")

    assert baseline_response.status_code == 200, baseline_response.text
    assert baseline_response.json()["is_baseline"] is True
    locked = service.run_evaluation(
        completed.id,
        ragas_adapter=FakeRagasAdapter(),
        answer_preparer=lambda _question: {
            "answer": "this should not overwrite the baseline",
            "sources": [],
            "retrieval_trace": {},
        },
    )

    detail = service.get_run_detail(locked.id)
    assert locked.is_baseline is True
    assert locked.status == "completed"
    assert detail is not None
    assert detail.samples[0].response != "this should not overwrite the baseline"


def test_golden_testset_import_validates_required_fields(client: TestClient, db_session):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)

    missing_reference = client.post(
        "/api/v1/evaluations/testsets",
        json={
            "knowledge_base_id": kb_id,
            "name": "法律黄金集",
            "items": [
                {
                    "question": "行政复议法的施行日期是什么？",
                    "expected_chunk_ids": ["chunk-ragas-eval-0"],
                }
            ],
        },
    )
    missing_source = client.post(
        "/api/v1/evaluations/testsets",
        json={
            "knowledge_base_id": kb_id,
            "name": "法律黄金集",
            "items": [
                {
                    "question": "行政复议法的施行日期是什么？",
                    "reference_answer": "自 2024 年 1 月 1 日起施行。",
                }
            ],
        },
    )

    assert missing_reference.status_code == 400
    assert "缺少标准答案" in missing_reference.text
    assert missing_source.status_code == 400
    assert "缺少 expected source" in missing_source.text


def test_golden_testset_run_records_expected_source_diagnostics(client: TestClient, db_session):
    kb_id = _create_kb(client)
    _add_completed_document_with_chunks(db_session, kb_id)
    testset_response = client.post(
        "/api/v1/evaluations/testsets",
        json={
            "knowledge_base_id": kb_id,
            "name": "法律黄金集",
            "items": [
                {
                    "question": "行政复议法的施行日期是什么？",
                    "reference_answer": "自 2024 年 1 月 1 日起施行。",
                    "expected_chunk_ids": ["chunk-ragas-eval-0"],
                    "expected_law_name": "中华人民共和国行政复议法",
                    "expected_article_no": "主席令第九号",
                    "tags": ["法条定位"],
                },
                {
                    "question": "行政处罚法法律责任的核心要点是什么？",
                    "reference_answer": "违法实施行政处罚需要责令改正并追究责任。",
                    "expected_chunk_ids": ["chunk-ragas-eval-1"],
                    "expected_law_name": "中华人民共和国行政处罚法",
                    "expected_article_no": "第七十六条",
                    "tags": ["法律责任"],
                },
                {
                    "question": "Quick Answer 评测关注什么？",
                    "reference_answer": "关注检索和回答质量。",
                    "expected_chunk_ids": ["chunk-ragas-eval-2"],
                    "tags": ["概括"],
                },
            ],
        },
    )
    assert testset_response.status_code == 201, testset_response.text
    testset_id = testset_response.json()["id"]
    service = EvaluationService(db_session, client.app.state.settings)
    run = service.create_run(knowledge_base_id=kb_id, testset_id=testset_id, testset_size=3)

    completed = service.run_evaluation(run.id, ragas_adapter=FakeRagasAdapter(), answer_preparer=_answer_preparer)

    assert completed.status == "completed"
    assert completed.testset_id == testset_id
    assert completed.testset_source == "golden"
    detail = service.get_run_detail(completed.id)
    assert detail is not None
    assert detail.samples[0].synthesizer_name == "golden:法律黄金集"
    assert detail.samples[0].expected_law_name == "中华人民共和国行政复议法"
    assert detail.samples[0].expected_chunk_ids == ["chunk-ragas-eval-0"]
    assert detail.samples[0].diagnostics["expected_source_hit"] is True
