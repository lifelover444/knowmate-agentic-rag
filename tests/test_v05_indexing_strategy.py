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
        "enable_parent_child": True,
        "enable_rerank": True,
        "enable_wiki": False,
        "enable_knowledge_graph": False,
    }


def test_search_normalizes_disabled_vector_strategy_to_v09_hybrid(client: TestClient):
    kb_id = _create_kb(client, {"enable_vector": False, "enable_keyword": True})

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "mode": "vector_only"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["diagnostics"]["mode"] == "hybrid"


def test_search_normalizes_disabled_keyword_strategy_to_v09_hybrid(client: TestClient):
    kb_id = _create_kb(client, {"enable_vector": True, "enable_keyword": False})

    response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "问题", "mode": "hybrid"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["diagnostics"]["mode"] == "hybrid"


def test_knowledge_base_update_can_enable_rerank_strategy(client: TestClient):
    kb_id = _create_kb(client)

    update_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={
            "indexing_strategy": {
                "enable_vector": True,
                "enable_keyword": True,
                "enable_parent_child": False,
                "enable_rerank": True,
                "enable_wiki": False,
                "enable_knowledge_graph": False,
            }
        },
    )

    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["indexing_strategy"]["enable_parent_child"] is True
    assert update_response.json()["indexing_strategy"]["enable_rerank"] is True
