from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge
from app.schemas.evaluation import EvaluationTestsetCreate, EvaluationTestsetItemCreate
from app.services.evaluation import EvaluationService
from app.services.evaluation_ab import EvaluationABService, parse_variant
from app.services.knowledge_search import KnowledgeSearchService
from app.services.legal_metadata import LegalMetadataBackfillService


def _create_legal_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "法律 A/B KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_legal_chunks(db_session, kb_id: str) -> None:
    db_session.add(
        Knowledge(
            id="doc-law-ab",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            source_type="file",
            title="中华人民共和国行政处罚法_20210122.pdf",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    for chunk_id, article, content in (
        (
            "chunk-law-76",
            "第七十六条",
            "第七十六条 行政机关违法实施行政处罚的，由上级行政机关责令改正。",
        ),
        (
            "chunk-law-83",
            "第八十三条",
            "第八十三条 对应当予以制止和处罚的违法行为不予制止、处罚的，应依法处分。",
        ),
    ):
        db_session.add(
            Chunk(
                id=chunk_id,
                tenant_id=10000,
                knowledge_base_id=kb_id,
                knowledge_id="doc-law-ab",
                content=content,
                search_text=f"中华人民共和国行政处罚法 {article} {content}",
                chunk_index=76 if chunk_id.endswith("76") else 83,
                is_enabled=True,
                start_at=0,
                end_at=len(content),
                chunk_type="child",
                context_header="# 第七章 法律责任",
                chunk_metadata={"title": "中华人民共和国行政处罚法_20210122.pdf"},
            )
        )
    db_session.commit()


def test_legal_metadata_backfill_updates_existing_chunks_and_vector_payload(client, db_session, fake_vector_store):
    kb_id = _create_legal_kb(client)
    _add_legal_chunks(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-law-76",
            "knowledge_id": "doc-law-ab",
            "knowledge_base_id": kb_id,
            "content": "第七十六条 行政机关违法实施行政处罚的，由上级行政机关责令改正。",
            "title": "中华人民共和国行政处罚法_20210122.pdf",
            "score": 1.0,
        }
    ]

    result = LegalMetadataBackfillService(
        db_session,
        client.app.state.settings,
        vector_store=fake_vector_store,
    ).backfill_knowledge_base(kb_id)

    chunk = db_session.get(Chunk, "chunk-law-76")
    assert result.scanned == 2
    assert result.updated == 2
    assert result.vector_synced == 2
    assert chunk.chunk_metadata["law_name"] == "中华人民共和国行政处罚法"
    assert chunk.chunk_metadata["article_no"] == "第七十六条"
    assert "第七十六条" in chunk.search_text
    assert fake_vector_store.results[0]["metadata"]["article_no"] == "第七十六条"


def test_evaluation_ab_report_includes_retrieval_metrics_and_stable_json(
    client,
    db_session,
    fake_vector_store,
    tmp_path,
):
    kb_id = _create_legal_kb(client)
    _add_legal_chunks(db_session, kb_id)
    LegalMetadataBackfillService(db_session, client.app.state.settings).backfill_knowledge_base(
        kb_id,
        sync_vector=False,
    )
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-law-76",
            "knowledge_id": "doc-law-ab",
            "knowledge_base_id": kb_id,
            "content": "第七十六条 行政机关违法实施行政处罚的，由上级行政机关责令改正。",
            "title": "中华人民共和国行政处罚法_20210122.pdf",
            "context_header": "# 第七章 法律责任",
            "chunk_type": "child",
            "metadata": {"law_name": "中华人民共和国行政处罚法", "article_no": "第七十六条"},
            "score": 1.0,
        },
        {
            "chunk_id": "chunk-law-83",
            "knowledge_id": "doc-law-ab",
            "knowledge_base_id": kb_id,
            "content": "第八十三条 对应当予以制止和处罚的违法行为不予制止、处罚的，应依法处分。",
            "title": "中华人民共和国行政处罚法_20210122.pdf",
            "context_header": "# 第七章 法律责任",
            "chunk_type": "child",
            "metadata": {"law_name": "中华人民共和国行政处罚法", "article_no": "第八十三条"},
            "score": 0.8,
        },
    ]
    testset = EvaluationService(db_session, client.app.state.settings).create_testset(
        EvaluationTestsetCreate(
            knowledge_base_id=kb_id,
            name="法律黄金集",
            items=[
                EvaluationTestsetItemCreate(
                    question="请说明中华人民共和国行政处罚法第七十六条的法律责任。",
                    reference_answer="违法实施行政处罚的，由上级行政机关责令改正。",
                    expected_chunk_ids=["chunk-law-76"],
                    expected_law_name="中华人民共和国行政处罚法",
                    expected_article_no="第七十六条",
                )
            ],
        )
    )

    service = EvaluationABService(
        db_session,
        client.app.state.settings,
        embedder=client.app.state.embedder,
        vector_store=fake_vector_store,
    )
    report = service.run_report(
        knowledge_base_id=kb_id,
        testset_id=testset.id,
        variants=[parse_variant("current:top_k=5,rerank=false")],
        tag="unit",
    )
    output = tmp_path / "ab-report.json"
    service.write_report(report, output)

    variant = report["variants"][0]
    assert variant["overall"] is None
    assert set(variant["metrics"]) >= {
        "context_precision",
        "context_recall",
        "faithfulness",
        "response_relevancy",
        "factual_correctness",
    }
    assert variant["recall_at_10"] == 1.0
    assert variant["precision_at_5"] == 1.0
    assert variant["failed_count"] == 0
    report_text = output.read_text(encoding="utf-8")
    assert "recall_at_10" in report_text
    assert "precision_at_5" in report_text


def test_legal_exact_lookup_recalls_arabic_article_query(client, db_session, fake_vector_store):
    kb_id = _create_legal_kb(client)
    _add_legal_chunks(db_session, kb_id)
    LegalMetadataBackfillService(db_session, client.app.state.settings).backfill_knowledge_base(
        kb_id,
        sync_vector=False,
    )
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-law-83",
            "knowledge_id": "doc-law-ab",
            "knowledge_base_id": kb_id,
            "content": "第八十三条 对应当予以制止和处罚的违法行为不予制止、处罚的，应依法处分。",
            "title": "中华人民共和国行政处罚法_20210122.pdf",
            "context_header": "# 第七章 法律责任",
            "chunk_type": "child",
            "metadata": {"law_name": "中华人民共和国行政处罚法", "article_no": "第八十三条"},
            "score": 1.0,
        }
    ]

    result = KnowledgeSearchService(
        db_session,
        client.app.state.settings,
        embedder=client.app.state.embedder,
        vector_store=fake_vector_store,
    ).search_with_diagnostics(
        knowledge_base_id=kb_id,
        query="请说明中华人民共和国行政处罚法 76 条的法律责任",
        top_k=5,
        enable_rerank=False,
    )

    stages = {stage["name"]: stage for stage in result.diagnostics["stages"]}
    assert result.hits[0].chunk_id == "chunk-law-76"
    assert stages["legal_exact_lookup"]["status"] == "done"
    assert stages["legal_exact_lookup"]["output"]["hit_count"] == 1


def test_legal_exact_lookup_recalls_numbered_knowledge_piece(client, db_session, fake_vector_store):
    kb_id = _create_legal_kb(client)
    _add_legal_chunks(db_session, kb_id)
    LegalMetadataBackfillService(db_session, client.app.state.settings).backfill_knowledge_base(
        kb_id,
        sync_vector=False,
    )
    fake_vector_store.results = []

    result = KnowledgeSearchService(
        db_session,
        client.app.state.settings,
        embedder=client.app.state.embedder,
        vector_store=fake_vector_store,
    ).search_with_diagnostics(
        knowledge_base_id=kb_id,
        query="请说明中华人民共和国行政处罚法第 2 个知识片段的核心法律要点",
        top_k=5,
        enable_rerank=False,
    )

    stages = {stage["name"]: stage for stage in result.diagnostics["stages"]}
    assert result.hits[0].chunk_id == "chunk-law-83"
    assert stages["legal_exact_lookup"]["status"] == "done"
