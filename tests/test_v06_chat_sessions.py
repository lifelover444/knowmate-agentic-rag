from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ChatMessage, ChatSession


def create_kb(client: TestClient, name: str = "chat session KB") -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name, "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_chat_session_crud_soft_delete_and_message_list(client):
    kb_id = create_kb(client)

    create_response = client.post(
        "/api/v1/chat-sessions",
        json={
            "knowledge_base_id": kb_id,
            "title": "第一轮问答",
            "settings": {"mode": "hybrid", "top_k": 5, "enable_query_rewrite": False},
        },
    )
    assert create_response.status_code == 201, create_response.text
    session = create_response.json()
    assert session["knowledge_base_id"] == kb_id
    assert session["title"] == "第一轮问答"
    assert session["is_pinned"] is False
    assert session["settings"]["top_k"] == 5

    patch_response = client.patch(
        f"/api/v1/chat-sessions/{session['id']}",
        json={"title": "已重命名", "is_pinned": True, "settings": {"mode": "vector_only", "top_k": 3}},
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["title"] == "已重命名"
    assert patch_response.json()["is_pinned"] is True

    list_response = client.get("/api/v1/chat-sessions")
    assert list_response.status_code == 200, list_response.text
    assert [item["id"] for item in list_response.json()["items"]] == [session["id"]]

    detail_response = client.get(f"/api/v1/chat-sessions/{session['id']}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["messages"] == []

    messages_response = client.get(f"/api/v1/chat-sessions/{session['id']}/messages")
    assert messages_response.status_code == 200, messages_response.text
    assert messages_response.json()["items"] == []

    delete_response = client.delete(f"/api/v1/chat-sessions/{session['id']}")
    assert delete_response.status_code == 204, delete_response.text

    assert client.get("/api/v1/chat-sessions").json()["items"] == []
    assert client.get(f"/api/v1/chat-sessions/{session['id']}").status_code == 404


def test_chat_session_list_filters_by_tenant(client, db_session):
    kb_id = create_kb(client)
    other_session = ChatSession(
        tenant_id=99999,
        knowledge_base_id=kb_id,
        title="其他租户会话",
        settings_json={},
    )
    db_session.add(other_session)
    db_session.commit()

    response = client.get("/api/v1/chat-sessions")

    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_message_search_groups_history_as_qa_pairs_and_stats(client, db_session):
    kb_id = create_kb(client, name="history search KB")
    create_response = client.post(
        "/api/v1/chat-sessions",
        json={"knowledge_base_id": kb_id, "title": "Redis 排障"},
    )
    assert create_response.status_code == 201, create_response.text
    session = create_response.json()

    user_message = ChatMessage(
        tenant_id=10000,
        session_id=session["id"],
        role="user",
        content="如何排查 Redis 连接错误？",
        original_query="如何排查 Redis 连接错误？",
        status="completed",
    )
    assistant_message = ChatMessage(
        tenant_id=10000,
        session_id=session["id"],
        role="assistant",
        content="可以检查 Redis URL、网络连通性和服务日志。",
        original_query="如何排查 Redis 连接错误？",
        status="completed",
    )
    db_session.add_all([user_message, assistant_message])
    db_session.commit()

    search_response = client.post("/api/v1/messages/search", json={"query": "服务日志", "limit": 10})

    assert search_response.status_code == 200, search_response.text
    payload = search_response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["session_id"] == session["id"]
    assert item["session_title"] == "Redis 排障"
    assert item["query_content"] == "如何排查 Redis 连接错误？"
    assert "服务日志" in item["answer_content"]
    assert "服务日志" in item["answer_snippet"]
    assert item["created_at"]
    assert item["match_type"] == "keyword"

    stats_response = client.get("/api/v1/messages/chat-history-stats")
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert stats["session_count"] == 1
    assert stats["message_count"] == 2
    assert stats["searchable"] is True
    assert stats["last_message_at"] is not None


def test_message_search_empty_result_and_bad_query_are_user_friendly(client):
    empty_response = client.post("/api/v1/messages/search", json={"query": "不存在的关键词"})
    assert empty_response.status_code == 200, empty_response.text
    assert empty_response.json() == {"items": [], "total": 0}

    bad_response = client.post("/api/v1/messages/search", json={"query": "   "})
    assert bad_response.status_code == 400
    assert "搜索关键词不能为空" in bad_response.text
