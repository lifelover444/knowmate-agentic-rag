from conftest import create_bound_models
from fastapi.testclient import TestClient


def _create_kb(client: TestClient, indexing_strategy: dict | None = None) -> str:
    chat_id, embedding_id = create_bound_models(client)
    payload = {
        "name": "strategy KB",
        "summary_model_id": chat_id,
        "embedding_model_id": embedding_id,
    }
    if indexing_strategy is not None:
        payload["indexing_strategy"] = indexing_strategy
    response = client.post("/api/v1/knowledge-bases", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_knowledge_base_has_default_indexing_strategy(client: TestClient):
    kb_id = _create_kb(client)

    response = client.get(f"/api/v1/knowledge-bases/{kb_id}")

    assert response.status_code == 200
    assert response.json()["indexing_strategy"] == {
        "enable_vector": True,
        "enable_keyword": True,
        "enable_parent_child": False,
        "enable_rerank": False,
        "enable_wiki": False,
        "enable_knowledge_graph": False,
    }


def test_search_rejects_mode_disabled_by_kb_indexing_strategy(client: TestClient):
    kb_id = _create_kb(client, {"enable_vector": False, "enable_keyword": True})

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "mode": "vector_only"},
    )

    assert response.status_code == 400
    assert "当前知识库未启用向量检索" in response.text


def test_search_rejects_hybrid_when_one_side_is_disabled(client: TestClient):
    kb_id = _create_kb(client, {"enable_vector": True, "enable_keyword": False})

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "mode": "hybrid"},
    )

    assert response.status_code == 400
    assert "混合检索需要同时启用向量检索和关键词检索" in response.text
