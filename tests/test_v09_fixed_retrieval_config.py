from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


class FixedScoreReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        return [(index, 0.7 - index * 0.01) for index, _ in enumerate(documents[:top_n])]


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "v0.9 fixed KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_rerank_model(client: TestClient) -> str:
    response = client.post(
        "/api/v1/models",
        json={
            "name": "v0.9 Rerank",
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


def _add_completed_document(db_session, kb_id: str) -> None:
    db_session.add(
        Knowledge(
            id="doc-v09-fixed",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="v0.9 固定主链路",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id="chunk-v09-fixed",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id="doc-v09-fixed",
            content="KnowMate v0.9 uses a fixed hybrid retrieval pipeline.",
            search_text="KnowMate v0.9 fixed hybrid retrieval pipeline",
            chunk_index=0,
            start_at=0,
            end_at=56,
        )
    )
    db_session.commit()


def test_retrieval_config_api_returns_v09_fixed_parameters(client: TestClient):
    response = client.put(
        "/api/v1/retrieval-config",
        json={
            "retrieval_mode": "vector_only",
            "vector_engine": "other",
            "keyword_engine": "postgres",
            "embedding_top_k": 3,
            "keyword_top_k": 4,
            "vector_threshold": 0.9,
            "keyword_threshold": 0.9,
            "rrf_k": 10,
            "rrf_vector_weight": 0.1,
            "rrf_keyword_weight": 0.9,
            "rrf_top_k": 5,
            "rerank_top_k": 3,
            "rerank_threshold": 0.7,
            "enable_rerank": False,
            "enable_parent_child": False,
            "parent_chunk_size": 1024,
            "child_chunk_size": 128,
            "chunk_overlap": 10,
            "final_context_count": 2,
            "max_context_chars": 1000,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["retrieval_mode"] == "hybrid"
    assert payload["vector_engine"] == "qdrant"
    assert payload["keyword_engine"] == "paradedb_bm25"
    assert payload["embedding_top_k"] == 50
    assert payload["keyword_top_k"] == 50
    assert payload["vector_threshold"] == 0.15
    assert payload["keyword_threshold"] == 0.2
    assert payload["rrf_k"] == 60
    assert payload["rrf_vector_weight"] == 0.65
    assert payload["rrf_keyword_weight"] == 0.35
    assert payload["rrf_top_k"] == 30
    assert payload["rerank_top_k"] == 8
    assert payload["rerank_threshold"] == 0.2
    assert payload["enable_rerank"] is True
    assert payload["enable_parent_child"] is True
    assert payload["parent_chunk_size"] == 4096
    assert payload["child_chunk_size"] == 384
    assert payload["chunk_overlap"] == 80
    assert payload["final_context_count"] == 6
    assert payload["max_context_chars"] == 8000


def test_new_knowledge_base_defaults_enable_parent_child_and_rerank(client: TestClient):
    kb_id = _create_kb(client)

    response = client.get(f"/api/v1/knowledge-bases/{kb_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["chunking_config"]["enable_parent_child"] is True
    assert payload["chunking_config"]["strategy"] == "auto"
    assert payload["chunking_config"]["chunk_size"] == 512
    assert payload["chunking_config"]["parent_chunk_size"] == 4096
    assert payload["chunking_config"]["child_chunk_size"] == 384
    assert payload["chunking_config"]["chunk_overlap"] == 80
    assert payload["chunking_config"]["separators"] == ["\n\n", "\n", "。"]
    assert payload["chunking_config"]["token_limit"] == 0
    assert payload["indexing_strategy"]["enable_parent_child"] is True
    assert payload["indexing_strategy"]["enable_rerank"] is True
    assert payload["capabilities"]["parent_child"] is True
    assert payload["capabilities"]["rerank"] is True


def test_knowledge_base_create_ignores_non_v09_chunking_overrides(client: TestClient):
    chat_id, embedding_id = create_bound_models(client)

    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "v0.9 fixed chunking KB",
            "embedding_model_id": embedding_id,
            "summary_model_id": chat_id,
            "chunking_config": {
                "strategy": "legacy",
                "chunk_size": 2048,
                "chunk_overlap": 5,
                "separators": ["|"],
                "token_limit": 128,
                "enable_parent_child": False,
                "parent_chunk_size": 1024,
                "child_chunk_size": 64,
            },
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["chunking_config"]["strategy"] == "auto"
    assert payload["chunking_config"]["chunk_size"] == 512
    assert payload["chunking_config"]["chunk_overlap"] == 80
    assert payload["chunking_config"]["separators"] == ["\n\n", "\n", "。"]
    assert payload["chunking_config"]["token_limit"] == 0
    assert payload["chunking_config"]["enable_parent_child"] is True
    assert payload["chunking_config"]["parent_chunk_size"] == 4096
    assert payload["chunking_config"]["child_chunk_size"] == 384


def test_quick_answer_normalizes_legacy_single_route_mode_to_hybrid(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = _create_kb(client)
    rerank_id = _create_rerank_model(client)
    config_response = client.put("/api/v1/retrieval-config", json={"rerank_model_id": rerank_id})
    assert config_response.status_code == 200, config_response.text
    _add_completed_document(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-v09-fixed",
            "knowledge_id": "doc-v09-fixed",
            "knowledge_base_id": kb_id,
            "content": "KnowMate v0.9 uses a fixed hybrid retrieval pipeline.",
            "title": "v0.9 固定主链路",
            "score": 0.91,
        }
    ]
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())

    response = client.post(
        "/api/v1/quick-answer",
        json={
            "knowledge_base_id": kb_id,
            "query": "What pipeline does KnowMate v0.9 use?",
            "mode": "vector_only",
            "enable_rerank": False,
        },
    )

    assert response.status_code == 200, response.text
    trace = response.json()["retrieval_trace"]
    assert trace["retrieval_mode"] == "hybrid"
    assert trace["diagnostics"]["mode"] == "hybrid"
    assert trace["diagnostics"]["enable_rerank"] is True
    stages = {stage["name"]: stage for stage in trace["stages"]}
    assert stages["vector"]["status"] == "done"
    assert stages["keyword"]["status"] == "done"
    assert stages["rrf"]["status"] == "done"
    assert stages["rerank"]["status"] == "done"
    retriever = trace["diagnostics"]["retrievers"][0]
    assert retriever["vector_engine"] == "qdrant"
    assert retriever["keyword_engine"] == "paradedb_bm25"
    assert response.json()["sources"][0]["retrieval_method"] == "hybrid"
