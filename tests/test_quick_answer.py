from conftest import create_bound_models
from fastapi.testclient import TestClient


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "quick answer KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_quick_answer_uses_retrieved_sources(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-1",
            "knowledge_id": "doc-1",
            "knowledge_base_id": kb_id,
            "content": "Knowmate answers from private documents.",
            "score": 0.91,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What does Knowmate do?", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answer"] == "Knowmate answers from private documents."
    assert payload["sources"][0]["chunk_id"] == "chunk-1"
    assert payload["sources"][0]["score"] == 0.91


def test_quick_answer_returns_fallback_without_sources(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = []

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "Unknown?", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answer"] == "没有在知识库中找到可引用的内容。"
    assert payload["sources"] == []
