from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge
from app.schemas.knowledge_search import KnowledgeSearchRequest
from app.schemas.quick_answer import QuickAnswerRequest


class FixedScoreReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        return [(index, 1.0 - index * 0.01) for index in range(min(len(documents), top_n))]


def _create_rerank_model(client: TestClient) -> str:
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


def _configure_rerank(client: TestClient) -> str:
    rerank_id = _create_rerank_model(client)
    response = client.put("/api/v1/retrieval-config", json={"rerank_model_id": rerank_id})
    assert response.status_code == 200, response.text
    return rerank_id


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "v0.9 hybrid entry", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_many_chunks(db_session, kb_id: str, *, count: int = 40) -> None:
    db_session.add(
        Knowledge(
            id="doc-v09-hybrid-entry",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="v0.9 hybrid entry",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    for index in range(count):
        db_session.add(
            Chunk(
                id=f"chunk-v09-hybrid-{index}",
                tenant_id=10000,
                knowledge_base_id=kb_id,
                knowledge_id="doc-v09-hybrid-entry",
                content=f"common hybrid retrieval content {index}",
                search_text=f"common hybrid retrieval content {index}",
                chunk_index=index,
                start_at=index * 10,
                end_at=index * 10 + 8,
                chunk_type="child",
                parent_chunk_id="parent-v09-hybrid",
                chunk_metadata={"title": "v0.9 hybrid entry"},
            )
        )
    db_session.commit()


def test_public_retrieval_requests_do_not_expose_legacy_mode_field():
    assert "mode" not in KnowledgeSearchRequest.model_fields
    assert "mode" not in QuickAnswerRequest.model_fields


def test_quick_answer_fixed_hybrid_entry_uses_top50_and_rrf_top30(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = _create_kb(client)
    _configure_rerank(client)
    _add_many_chunks(db_session, kb_id)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    fake_vector_store.results = [
        {
            "chunk_id": f"chunk-v09-hybrid-{index}",
            "knowledge_id": "doc-v09-hybrid-entry",
            "knowledge_base_id": kb_id,
            "content": f"common hybrid retrieval content {index}",
            "title": "v0.9 hybrid entry",
            "score": 0.95 - index * 0.001,
            "chunk_type": "child",
            "parent_chunk_id": "parent-v09-hybrid",
            "metadata": {"title": "v0.9 hybrid entry"},
        }
        for index in range(40)
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={
            "knowledge_base_id": kb_id,
            "query": "common hybrid",
            "mode": "keyword_only",
            "top_k": 2,
        },
    )

    assert response.status_code == 200, response.text
    trace = response.json()["retrieval_trace"]
    assert trace["retrieval_mode"] == "hybrid"
    stages = {stage["name"]: stage for stage in trace["stages"]}
    assert stages["vector"]["status"] == "done"
    assert stages["vector"]["input"]["limit"] == 50
    assert stages["keyword"]["status"] == "done"
    assert stages["keyword"]["input"]["limit"] == 50
    assert stages["rrf"]["status"] == "done"
    assert stages["rrf"]["output"]["output_count"] == 30
    assert stages["context_select"]["status"] == "done"
    assert stages["context_select"]["output"]["selected_context_count"] == 1
    assert len(response.json()["sources"]) == 1
