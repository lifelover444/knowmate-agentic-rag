from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.opensearch_store import OpenSearchSparseStore
from app.integrations.vector_store import VectorStoreRegistry


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


def test_vector_store_types_api_lists_availability_and_field_metadata(client: TestClient):
    response = client.get("/api/v1/vector-stores/types")

    assert response.status_code == 200, response.text
    items = response.json()
    qdrant = next(item for item in items if item["type"] == "qdrant")
    opensearch = next(item for item in items if item["type"] == "opensearch")
    tencent = next(item for item in items if item["type"] == "tencent_vectordb")

    assert qdrant["status"] == "available"
    assert qdrant["connection_fields"][0]["name"] == "host"
    assert any(field["name"] == "api_key" and field["sensitive"] for field in qdrant["connection_fields"])
    assert any(field["name"] == "collection_name" for field in qdrant["index_fields"])
    assert opensearch["status"] == "planned"
    assert tencent["status"] == "planned"


def test_non_qdrant_vector_store_create_fails_clearly_without_echoing_secret(client: TestClient):
    response = client.post(
        "/api/v1/vector-stores",
        json={
            "name": "OpenSearch",
            "provider": "opensearch",
            "config_json": {"endpoint": "https://search.example.com", "api_key": "secret-opensearch-key"},
        },
    )

    assert response.status_code == 400
    assert "当前版本仅支持 Qdrant VectorStore" in response.text
    assert "opensearch" in response.text
    assert "secret-opensearch-key" not in response.text


def test_vector_store_registry_builds_fake_opensearch_sparse_store():
    settings = Settings()
    store = VectorStoreRegistry(settings).build("opensearch", {"fake": True, "index_name": "knowmate-test"})

    assert isinstance(store, OpenSearchSparseStore)
    store.test_connection()


def test_vector_store_registry_rejects_unconfigured_opensearch_provider():
    settings = Settings()
    try:
        VectorStoreRegistry(settings).build("opensearch", {})
    except ValueError as exc:
        assert "OpenSearch/Elasticsearch VectorStore 未配置" in str(exc)
    else:
        raise AssertionError("expected unconfigured OpenSearch provider to fail clearly")
