from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


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


def test_knowledge_search_supports_keyword_only_and_returns_method_scores(client, db_session):
    kb_id = create_kb(client)
    add_completed_document(db_session, kb_id)

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "混合检索", "mode": "keyword_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    assert [hit["chunk_id"] for hit in hits] == ["chunk-keyword"]
    assert hits[0]["retrieval_method"] == "keyword"
    assert hits[0]["keyword_score"] > 0


def test_quick_answer_uses_hybrid_pipeline_and_keeps_source_metadata(client, db_session, fake_vector_store):
    kb_id = create_kb(client)
    add_completed_document(db_session, kb_id)
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


def test_knowledge_search_requires_rerank_model_when_enabled(client):
    kb_id = create_kb(client)

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "enable_rerank": True},
    )

    assert response.status_code == 400
    assert "Rerank" in response.text or "重排" in response.text
