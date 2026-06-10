from conftest import FixedScoreReranker, configure_rerank, create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge


def _create_kb_with_chunk(client: TestClient, db_session, *, chunk_id: str = "chunk-api") -> tuple[str, str, str]:
    chat_id, embedding_id = create_bound_models(client)
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "Chunk API KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert kb_response.status_code == 201, kb_response.text
    kb_id = kb_response.json()["id"]
    document_id = "doc-chunk-api"
    db_session.add(
        Knowledge(
            id=document_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            source_type="file",
            title="Chunk API 文档",
            source="manual",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id=chunk_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document_id,
            content="原始 chunk 内容",
            search_text="原始 chunk 内容",
            chunk_index=0,
            is_enabled=True,
            start_at=0,
            end_at=10,
            chunk_metadata={"title": "Chunk API 文档", "section": "old"},
        )
    )
    db_session.commit()
    return kb_id, document_id, chunk_id


def test_chunk_by_id_and_update_refresh_document_chunk_list(client: TestClient, db_session):
    _kb_id, document_id, chunk_id = _create_kb_with_chunk(client, db_session)

    by_id_response = client.get(f"/api/v1/chunks/by-id/{chunk_id}")

    assert by_id_response.status_code == 200, by_id_response.text
    assert by_id_response.json()["id"] == chunk_id
    assert by_id_response.json()["metadata"]["section"] == "old"

    update_response = client.put(
        f"/api/v1/chunks/{document_id}/{chunk_id}",
        json={
            "content": "更新后的 chunk 内容",
            "search_text": "更新后的 chunk 内容 可检索",
            "metadata": {"title": "Chunk API 文档", "section": "new"},
            "is_enabled": True,
        },
    )

    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["chunk"]["content"] == "更新后的 chunk 内容"
    assert payload["chunk"]["metadata"]["section"] == "new"
    assert payload["requires_reindex"] is True

    list_response = client.get(f"/api/v1/documents/{document_id}/chunks")
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()[0]["content"] == "更新后的 chunk 内容"
    assert list_response.json()[0]["metadata"]["section"] == "new"


def test_disabling_chunk_removes_it_from_quick_answer_retrieval(
    client: TestClient,
    db_session,
    fake_vector_store,
):
    kb_id, document_id, chunk_id = _create_kb_with_chunk(client, db_session, chunk_id="chunk-disable-api")
    fake_vector_store.results = [
        {
            "chunk_id": chunk_id,
            "knowledge_id": document_id,
            "knowledge_base_id": kb_id,
            "content": "禁用前可召回的 chunk 内容",
            "title": "Chunk API 文档",
            "score": 0.91,
            "is_enabled": True,
        }
    ]

    update_response = client.put(
        f"/api/v1/chunks/{document_id}/{chunk_id}",
        json={"is_enabled": False},
    )

    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["chunk"]["is_enabled"] is False
    assert fake_vector_store.results[0]["is_enabled"] is False

    answer_response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "禁用前可召回", "mode": "vector_only", "top_k": 5},
    )
    assert answer_response.status_code == 200, answer_response.text
    assert answer_response.json()["sources"] == []


def test_generated_questions_update_chunk_metadata_search_and_recommendations(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    kb_id, document_id, chunk_id = _create_kb_with_chunk(client, db_session, chunk_id="chunk-generated-api")
    fake_vector_store.results = [
        {
            "chunk_id": chunk_id,
            "knowledge_id": document_id,
            "knowledge_base_id": kb_id,
            "content": "原始 chunk 内容",
            "title": "Chunk API 文档",
            "score": 0.91,
            "metadata": {"title": "Chunk API 文档", "section": "old"},
        }
    ]

    add_response = client.post(
        f"/api/v1/chunks/by-id/{chunk_id}/questions",
        json={"question": "如何通过生成问题召回 chunk？"},
    )

    assert add_response.status_code == 201, add_response.text
    chunk = add_response.json()
    generated = chunk["metadata"]["generated_questions"]
    assert generated[0]["id"]
    assert generated[0]["question"] == "如何通过生成问题召回 chunk？"
    assert fake_vector_store.results[0]["metadata"]["generated_questions"] == generated

    search_response = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "生成问题召回", "mode": "keyword_only", "top_k": 5},
    )
    assert search_response.status_code == 200, search_response.text
    assert [hit["chunk_id"] for hit in search_response.json()["hits"]] == [chunk_id]
    assert search_response.json()["hits"][0]["metadata"]["generated_questions"] == generated

    recommended_response = client.get(
        "/api/v1/chat-sessions/recommended-questions",
        params={"knowledge_base_id": kb_id, "limit": 3},
    )
    assert recommended_response.status_code == 200, recommended_response.text
    assert recommended_response.json()["items"][0]["question"] == "如何通过生成问题召回 chunk？"

    delete_response = client.request(
        "DELETE",
        f"/api/v1/chunks/by-id/{chunk_id}/questions",
        json={"question_id": generated[0]["id"]},
    )

    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["metadata"].get("generated_questions") == []
    assert fake_vector_store.results[0]["metadata"].get("generated_questions") == []
    assert "生成问题召回" not in fake_vector_store.results[0]["search_text"]
    search_after_delete = client.post(
        "/api/v1/knowledge-search",
        json={"knowledge_base_id": kb_id, "query": "生成问题召回", "mode": "keyword_only", "top_k": 5},
    )
    assert search_after_delete.status_code == 200, search_after_delete.text
    hits_after_delete = search_after_delete.json()["hits"]
    assert [hit["chunk_id"] for hit in hits_after_delete] == [chunk_id]
    assert hits_after_delete[0]["keyword_score"] is None
