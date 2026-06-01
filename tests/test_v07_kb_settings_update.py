from conftest import create_bound_models
from fastapi.testclient import TestClient


def create_rerank_model(client: TestClient) -> str:
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Test Rerank",
            "type": "Rerank",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1",
            "api_key": "sk-test-1234",
            "model_name": "gte-rerank",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_kb_update_accepts_model_parser_chunking_indexing_and_vector_store(client: TestClient):
    chat_id, embedding_id = create_bound_models(client)
    next_chat_id, next_embedding_id = create_bound_models(client)
    rerank_id = create_rerank_model(client)
    vector_store = client.post(
        "/api/v1/vector-stores",
        json={
            "name": "KB Settings Qdrant",
            "provider": "qdrant",
            "config_json": {"host": "localhost", "port": 6333},
            "status": "active",
        },
    ).json()
    kb = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "settings KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    ).json()

    response = client.put(
        f"/api/v1/knowledge-bases/{kb['id']}",
        json={
            "name": "settings KB updated",
            "description": "updated from settings panel",
            "summary_model_id": next_chat_id,
            "embedding_model_id": next_embedding_id,
            "vector_store_id": vector_store["id"],
            "parser_engine_rules": [{"file_types": ["pdf", "txt"], "engine": "builtin"}],
            "chunking_config": {
                "strategy": "heading",
                "chunk_size": 768,
                "chunk_overlap": 96,
                "separators": ["\n\n", "。"],
                "token_limit": 512,
                "languages": ["zh", "en"],
                "enable_parent_child": True,
                "parent_chunk_size": 4096,
                "child_chunk_size": 384,
            },
            "indexing_strategy": {
                "enable_vector": True,
                "enable_keyword": False,
                "enable_parent_child": True,
                "enable_rerank": True,
                "enable_wiki": True,
                "enable_knowledge_graph": True,
                "rerank_model_id": rerank_id,
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "settings KB updated"
    assert payload["summary_model_id"] == next_chat_id
    assert payload["embedding_model_id"] == next_embedding_id
    assert payload["vector_store_id"] == vector_store["id"]
    assert payload["parser_engine_rules"] == [{"file_types": ["pdf", "txt"], "engine": "builtin"}]
    assert payload["chunking_config"]["strategy"] == "heading"
    assert payload["chunking_config"]["enable_parent_child"] is True
    assert payload["indexing_strategy"]["enable_keyword"] is False
    assert payload["indexing_strategy"]["enable_parent_child"] is True
    assert payload["indexing_strategy"]["enable_rerank"] is True
    assert payload["indexing_strategy"]["enable_wiki"] is False
    assert payload["indexing_strategy"]["enable_knowledge_graph"] is False


def test_kb_update_rejects_wrong_model_types_with_chinese_error(client: TestClient):
    chat_id, embedding_id = create_bound_models(client)
    kb = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "settings model validation KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    ).json()

    response = client.put(
        f"/api/v1/knowledge-bases/{kb['id']}",
        json={"embedding_model_id": chat_id},
    )

    assert response.status_code == 400
    assert "模型类型不匹配" in response.text
