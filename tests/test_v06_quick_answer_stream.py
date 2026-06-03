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


class RewriteFailingHistoryChatModel:
    def __init__(self) -> None:
        self.last_stream_messages = []

    def complete(self, messages, temperature=0.2):
        raise RuntimeError("rewrite failed")

    def stream_complete(self, messages, temperature=0.2):
        self.last_stream_messages = messages
        yield "历史回答"


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
    assert messages[1].prompt_context_summary
    assert "流式文档" in messages[1].prompt_context_summary
    assert messages[1].rendered_context
    assert "sk-test" not in json.dumps(messages[1].model_config_json, ensure_ascii=False)


def test_quick_answer_stream_saves_attachment_metadata_and_truncation(client, fake_vector_store, db_session):
    kb_id = create_kb(client)
    fake_vector_store.results = []
    attachment_text = "\n".join(f"第 {index} 行附件内容" for index in range(260))

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={
            "knowledge_base_id": kb_id,
            "query": "附件中有哪些内容？",
            "mode": "vector_only",
            "attachments": [
                {
                    "filename": "meeting.md",
                    "mime_type": "text/markdown",
                    "content": attachment_text,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    final = dict(parse_sse_events(response.text))["final"]
    trace = final["retrieval_trace"]
    assert trace["attachments_used"] is True
    assert trace["attachments_truncated"] is True
    assert trace["attachments"][0]["filename"] == "meeting.md"
    assert trace["attachments"][0]["truncated"] is True
    assert final["sources"] == []
    assert "第 0 行附件内容" in final["answer"]
    assert "<attachments>" in final["assistant_message"]["rendered_context"]

    messages = db_session.query(ChatMessage).order_by(ChatMessage.created_at).all()
    assert messages[0].model_config_json["attachments"][0]["filename"] == "meeting.md"
    assert messages[0].model_config_json["attachments"][0]["truncated"] is True
    assert messages[1].retrieval_trace_json["attachments_used"] is True
    assert messages[1].sources_json == []
    assert fake_vector_store.points == []


def test_quick_answer_stream_trace_marks_inapplicable_retrieval_stages_skipped(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-stream-vector",
            "knowledge_id": "doc-stream-vector",
            "knowledge_base_id": kb_id,
            "content": "流式向量检索返回来源。",
            "title": "流式向量文档",
            "score": 0.93,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "流式向量检索是什么？", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    trace = dict(parse_sse_events(response.text))["final"]["retrieval_trace"]
    stages = {stage["name"]: stage for stage in trace["stages"]}
    assert stages["vector"]["status"] == "done"
    assert stages["keyword"]["status"] == "skipped"
    assert stages["rrf"]["status"] == "skipped"
    assert stages["parent_expand"]["status"] == "done"
    assert stages["deduplicate"]["status"] == "done"
    assert stages["rerank"]["status"] == "skipped"


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


def test_quick_answer_stream_merges_recent_history_when_rewrite_fails(client, fake_vector_store):
    kb_id = create_kb(client)
    model = RewriteFailingHistoryChatModel()
    client.app.state.chat_model = model
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-history",
            "knowledge_id": "doc-history",
            "knowledge_base_id": kb_id,
            "content": "知友支持多轮追问。",
            "score": 0.91,
        }
    ]
    first = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "第一轮问题是什么？", "mode": "vector_only"},
    )
    session_id = dict(parse_sse_events(first.text))["session"]["id"]

    second = client.post(
        "/api/v1/quick-answer/stream",
        json={
            "session_id": session_id,
            "knowledge_base_id": kb_id,
            "query": "那它怎么继续？",
            "mode": "vector_only",
            "enable_query_rewrite": True,
        },
    )

    assert second.status_code == 200, second.text
    final = dict(parse_sse_events(second.text))["final"]
    trace = final["retrieval_trace"]
    prompt = model.last_stream_messages[-1]["content"]
    assert trace["rewrite_failed"] is True
    assert trace["history_used"] is True
    assert trace["history_message_count"] == 2
    assert "Conversation history:" in prompt
    assert "第一轮问题是什么？" in prompt
    assert "历史回答" in prompt


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
