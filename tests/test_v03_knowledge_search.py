from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


class FixedScoreReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        return [(index, 1.0 - index * 0.1) for index in range(min(len(documents), top_n))]


def create_rerank_model(client: TestClient) -> str:
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Test Rerank",
            "type": "Rerank",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1/reranks",
            "api_key": "sk-test-1234",
            "model_name": "qwen3-rerank",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def configure_rerank(client: TestClient) -> str:
    rerank_id = create_rerank_model(client)
    response = client.put("/api/v1/retrieval-config", json={"rerank_model_id": rerank_id})
    assert response.status_code == 200, response.text
    return rerank_id


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "v0.3 KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_completed_document(db_session, kb_id: str, *, document_id: str = "doc-v03") -> None:
    db_session.add(
        Knowledge(
            id=document_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="检索文档",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id="chunk-keyword",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content="知友支持混合检索和来源展示",
            search_text="知友 支持 混合 检索 来源 展示",
            chunk_index=0,
            start_at=0,
            end_at=15,
        )
    )
    db_session.commit()


def test_knowledge_search_normalizes_keyword_only_to_hybrid_and_returns_method_scores(
    client,
    db_session,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    add_completed_document(db_session, kb_id)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "keyword_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    assert [hit["chunk_id"] for hit in hits] == ["chunk-keyword"]
    assert hits[0]["title"] == "检索文档"
    assert hits[0]["retrieval_method"] == "hybrid"
    assert hits[0]["keyword_score"] > 0
    assert response.json()["diagnostics"]["mode"] == "hybrid"


def test_knowledge_search_returns_hybrid_retrieval_diagnostics(client, db_session, fake_vector_store, monkeypatch):
    kb_id = create_kb(client)
    rerank_id = configure_rerank(client)
    add_completed_document(db_session, kb_id)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-keyword",
            "knowledge_id": "doc-v03",
            "knowledge_base_id": kb_id,
            "content": "知友支持混合检索和来源展示",
            "title": "检索文档",
            "score": 0.88,
        }
    ]

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "hybrid", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    stages = {stage["name"]: stage for stage in payload["diagnostics"]["stages"]}
    assert stages["vector"]["status"] == "done"
    assert stages["vector"]["output"]["hit_count"] == 1
    assert stages["keyword"]["status"] == "done"
    assert stages["keyword"]["output"]["hit_count"] == 1
    assert stages["rrf"]["status"] == "done"
    assert stages["parent_expand"]["status"] == "done"
    assert stages["deduplicate"]["status"] == "done"
    assert stages["rerank"]["status"] == "done"
    assert stages["rerank"]["output"]["rerank_input_count"] == 1
    assert stages["rerank"]["output"]["model_config_used"] == rerank_id
    assert stages["rrf"]["output"]["output_count"] == 1
    retriever = payload["diagnostics"]["retrievers"][0]
    assert retriever["knowledge_base_id"] == kb_id
    assert retriever["engine"] == "qdrant+paradedb_bm25"
    assert retriever["vector_engine"] == "qdrant"
    assert retriever["keyword_engine"] == "paradedb_bm25"
    assert retriever["mode"] == "hybrid"
    assert retriever["hit_count"] == 1


def test_knowledge_search_keeps_weknora_style_over_retrieval_pool(client, fake_vector_store, monkeypatch):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": f"chunk-over-retrieval-{index}",
            "knowledge_id": f"doc-over-retrieval-{index}",
            "knowledge_base_id": kb_id,
            "content": f"over retrieval candidate {index}",
            "title": "候选池文档",
            "score": 1.0 - index * 0.001,
        }
        for index in range(60)
    ]

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "候选池放大", "mode": "hybrid"},
    )

    assert response.status_code == 200, response.text
    stages = {stage["name"]: stage for stage in response.json()["diagnostics"]["stages"]}
    assert stages["vector"]["output"]["hit_count"] == 50
    assert stages["rrf"]["input"]["vector_count"] == 50
    assert stages["rrf"]["output"]["output_count"] == 50
    assert stages["rerank"]["output"]["rerank_input_count"] == 50


def test_knowledge_search_expands_low_recall_query_with_keyword_variants(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = []
    db_session.add(
        Knowledge(
            id="doc-query-expansion",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="交通事故保险责任",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id="chunk-query-expansion",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id="doc-query-expansion",
            content="交强险和商业三者险的赔付顺序说明。",
            search_text="交强险 商业三者险",
            chunk_index=0,
            start_at=0,
            end_at=18,
            chunk_type="text",
            chunk_metadata={"title": "交通事故保险责任"},
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/knowledge-search",
        json={
            "knowledge_base_id": kb_id,
            "query": "请问这个问题涉及很多背景、交强险 商业三者险、其他无关描述一二三四五六七八九十怎么赔付",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [hit["chunk_id"] for hit in payload["hits"]] == ["chunk-query-expansion"]
    stages = {stage["name"]: stage for stage in payload["diagnostics"]["stages"]}
    assert stages["query_expansion"]["status"] == "done"
    assert "交强险 商业三者险" in stages["query_expansion"]["output"]["variants"]
    assert stages["query_expansion"]["output"]["added_hit_count"] == 1


def test_knowledge_search_faq_merge_boosts_high_confidence_faq_and_traces_stage(
    client,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-doc-policy",
            "knowledge_id": "doc-policy",
            "knowledge_base_id": kb_id,
            "content": "普通文档说明退款流程需要三个工作日。",
            "title": "退款文档",
            "chunk_type": "text",
            "score": 0.9,
            "metadata": {},
        },
        {
            "chunk_id": "chunk-faq-refund",
            "knowledge_id": "faq-refund",
            "knowledge_base_id": kb_id,
            "content": "怎么申请退款？\n在订单页面提交退款申请。",
            "title": "怎么申请退款？",
            "chunk_type": "faq",
            "score": 0.82,
            "metadata": {
                "source_type": "faq",
                "standard_question": "怎么申请退款？",
                "matched_question": "退款怎么操作？",
                "question_role": "similar",
                "index_mode": "question_answer",
            },
        },
    ]

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "退款怎么操作？", "mode": "vector_only", "top_k": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [hit["chunk_id"] for hit in payload["hits"]] == ["chunk-faq-refund", "chunk-doc-policy"]
    faq = payload["hits"][0]
    assert faq["score"] > 0.9
    assert faq["metadata"]["matched_question"] == "退款怎么操作？"
    assert faq["metadata"]["standard_question"] == "怎么申请退款？"
    assert faq["metadata"]["question_role"] == "similar"
    stages = {stage["name"]: stage for stage in payload["diagnostics"]["stages"]}
    assert stages["faq_merge"]["status"] == "done"
    assert stages["faq_merge"]["input"]["candidate_count"] == 2
    assert stages["faq_merge"]["output"]["output_count"] == 2
    assert stages["faq_merge"]["output"]["boost_count"] == 1
    assert stages["faq_merge"]["output"]["max_boost_factor"] > 1


def test_knowledge_search_faq_merge_does_not_promote_low_confidence_faq(
    client,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-doc-low",
            "knowledge_id": "doc-low",
            "knowledge_base_id": kb_id,
            "content": "文档命中内容。",
            "title": "文档",
            "chunk_type": "text",
            "score": 0.45,
            "metadata": {},
        },
        {
            "chunk_id": "chunk-faq-low",
            "knowledge_id": "faq-low",
            "knowledge_base_id": kb_id,
            "content": "低置信 FAQ。",
            "title": "FAQ",
            "chunk_type": "faq",
            "score": 0.3,
            "metadata": {
                "source_type": "faq",
                "standard_question": "标准问",
                "matched_question": "相似问",
                "question_role": "similar",
                "index_mode": "question_only",
            },
        },
    ]

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "低置信问题", "mode": "vector_only", "top_k": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [hit["chunk_id"] for hit in payload["hits"]] == ["chunk-doc-low", "chunk-faq-low"]
    stages = {stage["name"]: stage for stage in payload["diagnostics"]["stages"]}
    assert stages["faq_merge"]["output"]["boost_count"] == 0


def test_quick_answer_uses_hybrid_pipeline_and_keeps_source_metadata(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    add_completed_document(db_session, kb_id)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-keyword",
            "knowledge_id": "doc-v03",
            "knowledge_base_id": kb_id,
            "content": "知友支持混合检索和来源展示",
            "title": "检索文档",
            "score": 0.88,
        }
    ]

    response = client.post("/api/v1/quick-answer", json={"knowledge_base_id": kb_id, "query": "知友支持什么？"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sources"][0]["retrieval_method"] == "hybrid"
    assert payload["sources"][0]["vector_score"] == 0.88
    assert payload["sources"][0]["keyword_score"] > 0
    assert payload["sources"][0]["rrf_score"] > 0


def test_knowledge_search_reports_fixed_rerank_enabled_when_model_is_not_configured(client):
    kb_id = create_kb(client)

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "enable_rerank": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["diagnostics"]["enable_rerank"] is True
    stages = {stage["name"]: stage for stage in payload["diagnostics"]["stages"]}
    assert stages["rerank"]["status"] == "skipped"
    assert stages["rerank"]["output"]["reason"] == "no_hits"


def test_soft_deleted_document_chunks_are_excluded_from_keyword_and_hybrid_search(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    add_completed_document(db_session, kb_id, document_id="doc-deleted")
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-keyword",
            "knowledge_id": "doc-deleted",
            "knowledge_base_id": kb_id,
            "content": "知友支持混合检索和来源展示",
            "title": "检索文档",
            "score": 0.88,
        }
    ]

    before_delete = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "keyword_only", "top_k": 5},
    )
    assert before_delete.status_code == 200, before_delete.text
    assert [hit["chunk_id"] for hit in before_delete.json()["hits"]] == ["chunk-keyword"]

    delete_response = client.delete("/api/v1/documents/doc-deleted")
    assert delete_response.status_code == 204
    db_session.expire_all()

    keyword_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "keyword_only", "top_k": 5},
    )
    assert keyword_response.status_code == 200, keyword_response.text
    assert keyword_response.json()["hits"] == []

    hybrid_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "hybrid", "top_k": 5},
    )
    assert hybrid_response.status_code == 200, hybrid_response.text
    assert hybrid_response.json()["hits"] == []
