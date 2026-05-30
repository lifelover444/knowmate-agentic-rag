from conftest import create_bound_models
from fastapi.testclient import TestClient


def test_vector_store_crud_masks_secret_config_and_sets_default(client: TestClient):
    create_response = client.post(
        "/api/v1/vector-stores",
        json={
            "name": "Qdrant Remote",
            "provider": "qdrant",
            "config_json": {"host": "qdrant.local", "port": 6333, "api_key": "secret-key"},
            "status": "active",
            "is_default": True,
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["provider"] == "qdrant"
    assert created["is_default"] is True
    assert created["config_json"]["api_key_configured"] is True
    assert "secret-key" not in create_response.text

    list_response = client.get("/api/v1/vector-stores")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]

    update_response = client.put(
        f"/api/v1/vector-stores/{created['id']}",
        json={"name": "Qdrant Updated", "config_json": {"api_key": "new-secret"}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Qdrant Updated"
    assert "new-secret" not in update_response.text


def test_knowledge_base_can_bind_vector_store(client: TestClient):
    store = client.post(
        "/api/v1/vector-stores",
        json={
            "name": "Bound Qdrant",
            "provider": "qdrant",
            "config_json": {"host": "localhost", "port": 6333},
            "status": "active",
        },
    ).json()
    chat_id, embedding_id = create_bound_models(client)

    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "bound vector KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
            "vector_store_id": store["id"],
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["vector_store_id"] == store["id"]


def test_vector_store_test_endpoint_uses_registered_qdrant_provider(client: TestClient):
    response = client.post(
        "/api/v1/vector-stores/test",
        json={"provider": "qdrant", "config_json": {"host": "localhost", "port": 6333}},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "Qdrant" in response.json()["message"]
