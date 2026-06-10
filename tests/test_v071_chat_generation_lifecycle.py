import json

from conftest import FixedScoreReranker, configure_rerank, create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ChatMessage, Knowledge
from tests.test_v06_quick_answer_stream import parse_sse_events


class SelfStoppingChatModel:
    def __init__(self) -> None:
        self.stop_session_id = ""
        self.registry = None

    def complete(self, messages):
        raise AssertionError("stream endpoint should use stream_complete when available")

    def stream_complete(self, messages, temperature=0.2):
        yield "已"
        if self.registry is not None:
            self.registry.stop_session(self.stop_session_id, reason="用户已停止生成")
        yield "停止后不应发送"


def create_kb(client: TestClient, name: str = "v071 chat KB") -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name, "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_document(db_session, kb_id: str, document_id: str = "doc-chat-lifecycle") -> None:
    db_session.add(
        Knowledge(
            id=document_id,
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            source_type="file",
            title="模型配置手册",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            embedding_model_id="embedding-model",
        )
    )
    db_session.commit()


def add_vector_hit(fake_vector_store, kb_id: str, document_id: str = "doc-chat-lifecycle") -> None:
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-chat-lifecycle",
            "knowledge_id": document_id,
            "knowledge_base_id": kb_id,
            "content": "模型配置需要先创建 OpenAI-compatible QA 和 Embedding 模型。",
            "title": "模型配置手册",
            "score": 0.92,
        }
    ]


def test_stream_auto_titles_empty_session_and_persists_last_request_state(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    add_document(db_session, kb_id)
    add_vector_hit(fake_vector_store, kb_id)
    session_response = client.post("/api/v1/chat-sessions", json={"knowledge_base_id": kb_id, "title": "新会话"})
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={
            "session_id": session_id,
            "knowledge_base_id": kb_id,
            "knowledge_base_ids": [kb_id],
            "knowledge_ids": ["doc-chat-lifecycle"],
            "mentioned_items": [{"id": kb_id, "name": "v071 chat KB", "type": "kb", "kb_type": "document"}],
            "query": "如何配置模型和知识库？",
            "mode": "hybrid",
            "top_k": 7,
            "enable_rerank": False,
            "enable_query_rewrite": True,
        },
    )

    assert response.status_code == 200, response.text
    final = dict(parse_sse_events(response.text))["final"]
    assert final["answer"]
    assert final["retrieval_trace"]["rerank_hits"] == 1

    detail = client.get(f"/api/v1/chat-sessions/{session_id}")
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["title"] == "如何配置模型和知识库"
    state = payload["last_request_state"]
    assert state["status"] == "completed"
    assert state["query"] == "如何配置模型和知识库？"
    assert state["knowledge_base_ids"] == [kb_id]
    assert state["knowledge_ids"] == ["doc-chat-lifecycle"]
    assert state["top_k"] == 7
    assert state["mode"] == "hybrid"
    assert state["enable_rerank"] is False
    assert state["enable_query_rewrite"] is True
    assert state["hit_count"] == 1
    assert state["duration_ms"] >= 0
    assert "sk-test" not in json.dumps(state, ensure_ascii=False)


def test_stop_generation_cancels_active_stream_and_persists_partial_answer(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client, "stop chat KB")
    configure_rerank(client)
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())
    add_document(db_session, kb_id, "doc-stop-chat")
    add_vector_hit(fake_vector_store, kb_id)
    session = client.post("/api/v1/chat-sessions", json={"knowledge_base_id": kb_id, "title": "新会话"}).json()
    chat_model = SelfStoppingChatModel()
    chat_model.stop_session_id = session["id"]
    client.app.state.chat_model = chat_model

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"session_id": session["id"], "knowledge_base_id": kb_id, "query": "请生成很长的回答"},
    )

    assert response.status_code == 200, response.text
    events = parse_sse_events(response.text)
    event_names = [name for name, _data in events]
    assert "stopped" in event_names
    assert "final" not in event_names
    assert [data["text"] for name, data in events if name == "token"] == ["已"]
    stopped = dict(events)["stopped"]
    assert stopped["error_message"] == "用户已停止生成"

    assistant = db_session.query(ChatMessage).filter_by(role="assistant").one()
    assert assistant.content == "已"
    assert assistant.status == "cancelled"
    assert assistant.error_message == "用户已停止生成"

    detail = client.get(f"/api/v1/chat-sessions/{session['id']}")
    assert detail.json()["last_request_state"]["status"] == "cancelled"


def test_stop_generation_endpoint_returns_chinese_error_for_missing_session(client):
    response = client.post("/api/v1/chat-sessions/missing-session/stop", json={})

    assert response.status_code == 404
    assert "会话不存在" in response.text
