import json

from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ChatMessage, KnowledgeBase


class FakeStreamingChatModel:
    def complete(self, messages):
        raise AssertionError("stream endpoint should use stream_complete when available")

    def stream_complete(self, messages, temperature=0.2):
        yield "流"
        yield "式"


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "stream KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        name = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data = line.removeprefix("data: ").strip()
        if name:
            events.append((name, json.loads(data)))
    return events


def test_quick_answer_stream_creates_session_messages_and_final_sources(client, fake_vector_store, db_session):
    kb_id = create_kb(client)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-stream",
            "knowledge_id": "doc-stream",
            "knowledge_base_id": kb_id,
            "content": "流式回答会持续返回来源依据。",
            "title": "流式文档",
            "score": 0.93,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "流式回答是什么？", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse_events(response.text)
    event_names = [name for name, _data in events]
    assert event_names[:4] == ["session", "user_message", "rewrite", "retrieval"]
    assert "token" in event_names
    assert event_names[-2:] == ["final", "done"]

    final = dict(events)["final"]
    assert final["answer"] == "流式回答会持续返回来源依据。"
    assert final["sources"][0]["chunk_id"] == "chunk-stream"
    assert final["retrieval_trace"]["original_query"] == "流式回答是什么？"
    assert final["retrieval_trace"]["rewrite_enabled"] is False

    messages = db_session.query(ChatMessage).order_by(ChatMessage.created_at).all()
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "流式回答是什么？"
    assert messages[1].status == "completed"
    assert messages[1].sources_json[0]["chunk_id"] == "chunk-stream"
    assert "sk-test" not in json.dumps(messages[1].model_config_json, ensure_ascii=False)


def test_quick_answer_stream_missing_model_config_returns_chinese_error(client, fake_vector_store, db_session):
    kb_id = "kb-missing-model"
    db_session.add(
        KnowledgeBase(
            id=kb_id,
            tenant_id=10000,
            name="missing model KB",
            kb_type="document",
            chunking_config={},
            indexing_strategy={},
            embedding_model_id="missing-embedding",
            summary_model_id="missing-chat",
        )
    )
    db_session.commit()
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-missing-model",
            "knowledge_id": "doc-missing-model",
            "knowledge_base_id": kb_id,
            "content": "需要真实 QA 模型才能回答。",
            "score": 0.9,
        }
    ]
    client.app.state.chat_model = None

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "问题", "mode": "vector_only"},
    )

    assert response.status_code == 404
    assert "模型" in response.text


def test_quick_answer_stream_query_rewrite_trace_enabled_with_history(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-rewrite",
            "knowledge_id": "doc-rewrite",
            "knowledge_base_id": kb_id,
            "content": "改写后的检索仍然返回来源。",
            "score": 0.91,
        }
    ]
    first = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "第一轮问题", "mode": "vector_only"},
    )
    session_id = dict(parse_sse_events(first.text))["session"]["id"]

    second = client.post(
        "/api/v1/quick-answer/stream",
        json={
            "session_id": session_id,
            "knowledge_base_id": kb_id,
            "query": "那它怎么用？",
            "mode": "vector_only",
            "enable_query_rewrite": True,
        },
    )

    assert second.status_code == 200, second.text
    final = dict(parse_sse_events(second.text))["final"]
    trace = final["retrieval_trace"]
    assert trace["original_query"] == "那它怎么用？"
    assert trace["rewrite_enabled"] is True
    assert trace["rewrite_skipped"] is False
    assert trace["rewrite_failed"] is False
    assert trace["rewritten_query"] == "fake answer"


def test_quick_answer_stream_uses_streaming_chat_client(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-stream-client",
            "knowledge_id": "doc-stream-client",
            "knowledge_base_id": kb_id,
            "content": "这个内容用于构造 prompt。",
            "score": 0.9,
        }
    ]
    client.app.state.chat_model = FakeStreamingChatModel()

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "测试真流式", "mode": "vector_only"},
    )

    assert response.status_code == 200, response.text
    events = parse_sse_events(response.text)
    tokens = [data["text"] for event, data in events if event == "token"]
    assert tokens == ["流", "式"]
    assert dict(events)["final"]["answer"] == "流式"
