from conftest import create_bound_models
from fastapi.testclient import TestClient


def _create_kb(
    client: TestClient,
    name: str,
    *,
    kb_type: str = "document",
    indexing_strategy: dict | None = None,
) -> dict:
    chat_id, embedding_id = create_bound_models(client)
    payload = {
        "name": name,
        "kb_type": kb_type,
        "summary_model_id": chat_id,
        "embedding_model_id": embedding_id,
    }
    if indexing_strategy is not None:
        payload["indexing_strategy"] = indexing_strategy
    response = client.post("/api/v1/knowledge-bases", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_knowledge_base_read_exposes_capabilities_and_default_pin_state(client: TestClient):
    kb = _create_kb(
        client,
        "capability KB",
        indexing_strategy={
            "enable_vector": True,
            "enable_keyword": False,
            "enable_parent_child": True,
            "enable_rerank": True,
            "enable_wiki": True,
            "enable_knowledge_graph": True,
        },
    )

    assert kb["is_pinned"] is False
    assert kb["pinned_at"] is None
    assert kb["capabilities"] == {
        "document": True,
        "faq": False,
        "vector": True,
            "keyword": True,
        "parent_child": True,
        "rerank": True,
        "wiki": False,
        "graph": False,
    }


def test_faq_knowledge_base_capabilities(client: TestClient):
    kb = _create_kb(client, "faq KB", kb_type="faq")

    assert kb["capabilities"]["document"] is False
    assert kb["capabilities"]["faq"] is True
    assert kb["capabilities"]["vector"] is True
    assert kb["capabilities"]["keyword"] is True


def test_pin_unpin_knowledge_base_and_list_pinned_first(client: TestClient):
    first = _create_kb(client, "first KB")
    second = _create_kb(client, "second KB")

    initial_list = client.get("/api/v1/knowledge-bases")
    assert initial_list.status_code == 200
    assert [item["id"] for item in initial_list.json()] == [second["id"], first["id"]]

    pin_response = client.put(f"/api/v1/knowledge-bases/{first['id']}/pin", json={"pinned": True})
    assert pin_response.status_code == 200, pin_response.text
    pinned = pin_response.json()
    assert pinned["id"] == first["id"]
    assert pinned["is_pinned"] is True
    assert pinned["pinned_at"] is not None

    pinned_list = client.get("/api/v1/knowledge-bases")
    assert pinned_list.status_code == 200
    assert [item["id"] for item in pinned_list.json()] == [first["id"], second["id"]]
    assert pinned_list.json()[0]["is_pinned"] is True

    unpin_response = client.put(f"/api/v1/knowledge-bases/{first['id']}/pin", json={"pinned": False})
    assert unpin_response.status_code == 200, unpin_response.text
    assert unpin_response.json()["is_pinned"] is False
    assert unpin_response.json()["pinned_at"] is None

    unpinned_list = client.get("/api/v1/knowledge-bases")
    assert [item["id"] for item in unpinned_list.json()] == [second["id"], first["id"]]


def test_soft_deleted_pinned_knowledge_base_is_not_listed(client: TestClient):
    kb = _create_kb(client, "pinned delete KB")
    pin_response = client.put(f"/api/v1/knowledge-bases/{kb['id']}/pin", json={"pinned": True})
    assert pin_response.status_code == 200, pin_response.text

    delete_response = client.delete(f"/api/v1/knowledge-bases/{kb['id']}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/knowledge-bases")
    assert list_response.status_code == 200
    assert list_response.json() == []

    repin_deleted = client.put(f"/api/v1/knowledge-bases/{kb['id']}/pin", json={"pinned": True})
    assert repin_deleted.status_code == 404
