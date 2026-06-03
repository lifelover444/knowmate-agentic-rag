from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ChatMessage, Chunk, Knowledge, KnowledgeBase
from app.services.quick_answer import _build_conversation_context


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "quick answer KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_completed_document(db_session, kb_id: str) -> None:
    db_session.add(
        Knowledge(
            id="doc-quick-trace",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="Quick Trace Doc",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id="chunk-quick-trace",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id="doc-quick-trace",
            content="Knowmate answers from private documents.",
            search_text="Knowmate answers private documents",
            chunk_index=0,
            start_at=0,
            end_at=40,
        )
    )
    db_session.commit()


class FailingReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        raise RuntimeError("rerank provider down")


class FixedScoreReranker:
    def rerank(self, *, query: str, documents: list[str], top_n: int):
        return [(0, 0.6), (1, 0.4)][:top_n]


def create_rerank_model(client: TestClient) -> str:
    response = client.post(
        "/api/v1/models",
        json={
            "name": "Test Rerank",
            "type": "Rerank",
            "provider": "qwen",
            "source": "remote",
            "base_url": "https://example.com/v1/reranks",
            "api_key": "sk-test-1234",
            "model_name": "qwen3-rerank",
        },
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


def test_quick_answer_response_includes_retrieval_diagnostic_stages(client, db_session, fake_vector_store):
    kb_id = create_kb(client)
    add_completed_document(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-quick-trace",
            "knowledge_id": "doc-quick-trace",
            "knowledge_base_id": kb_id,
            "content": "Knowmate answers from private documents.",
            "score": 0.91,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What does Knowmate do?", "mode": "hybrid", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    trace = response.json()["retrieval_trace"]
    stages = {stage["name"]: stage for stage in trace["stages"]}
    assert stages["vector"]["status"] == "done"
    assert stages["keyword"]["status"] == "done"
    assert stages["rrf"]["status"] == "done"
    assert stages["parent_expand"]["status"] == "done"
    assert stages["deduplicate"]["status"] == "done"
    assert stages["rerank"]["status"] == "skipped"
    assert stages["answer"]["status"] == "done"
    assert trace["diagnostics"]["mode"] == "hybrid"


def test_quick_answer_falls_back_when_rerank_provider_fails(client, db_session, fake_vector_store, monkeypatch):
    kb_id = create_kb(client)
    add_completed_document(db_session, kb_id)
    kb = db_session.get(KnowledgeBase, kb_id)
    kb.indexing_strategy = {
        "enable_vector": True,
        "enable_keyword": True,
        "enable_parent_child": True,
        "enable_rerank": True,
        "enable_wiki": False,
        "enable_knowledge_graph": False,
    }
    db_session.commit()
    rerank_id = create_rerank_model(client)
    config_response = client.put(
        "/api/v1/retrieval-config",
        json={
            "retrieval_mode": "vector_only",
            "embedding_top_k": 10,
            "vector_threshold": 0.15,
            "keyword_threshold": 0.3,
            "rerank_top_k": 5,
            "rerank_threshold": 0.2,
            "rerank_model_id": rerank_id,
            "enable_rerank": True,
            "rrf_k": 60,
            "rrf_vector_weight": 0.7,
            "rrf_keyword_weight": 0.3,
        },
    )
    assert config_response.status_code == 200, config_response.text
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-quick-trace",
            "knowledge_id": "doc-quick-trace",
            "knowledge_base_id": kb_id,
            "content": "Knowmate answers from private documents.",
            "title": "Quick Trace Doc",
            "score": 0.91,
        }
    ]
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FailingReranker())

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What does Knowmate do?", "mode": "vector_only"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sources"][0]["chunk_id"] == "chunk-quick-trace"
    stages = {stage["name"]: stage for stage in payload["retrieval_trace"]["stages"]}
    assert stages["rerank"]["status"] == "failed"
    assert stages["rerank"]["output"]["fallback"] is True
    assert "rerank provider down" in stages["rerank"]["error_message"]


def test_quick_answer_rerank_trace_records_threshold_degrade_and_mmr(
    client,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb_id = create_kb(client)
    kb = db_session.get(KnowledgeBase, kb_id)
    kb.indexing_strategy = {
        "enable_vector": True,
        "enable_keyword": True,
        "enable_parent_child": True,
        "enable_rerank": True,
        "enable_wiki": False,
        "enable_knowledge_graph": False,
    }
    db_session.commit()
    rerank_id = create_rerank_model(client)
    config_response = client.put(
        "/api/v1/retrieval-config",
        json={
            "retrieval_mode": "vector_only",
            "embedding_top_k": 10,
            "vector_threshold": 0.15,
            "keyword_threshold": 0.3,
            "rerank_top_k": 2,
            "rerank_threshold": 0.8,
            "rerank_model_id": rerank_id,
            "enable_rerank": True,
            "rrf_k": 60,
            "rrf_vector_weight": 0.7,
            "rrf_keyword_weight": 0.3,
        },
    )
    assert config_response.status_code == 200, config_response.text
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-rerank-a",
            "knowledge_id": "doc-rerank-a",
            "knowledge_base_id": kb_id,
            "content": "Knowmate rerank candidate A.",
            "title": "Rerank A",
            "score": 0.91,
        },
        {
            "chunk_id": "chunk-rerank-b",
            "knowledge_id": "doc-rerank-b",
            "knowledge_base_id": kb_id,
            "content": "Knowmate rerank candidate B.",
            "title": "Rerank B",
            "score": 0.9,
        },
    ]
    monkeypatch.setattr("app.services.knowledge_search.RerankerClient", lambda _config: FixedScoreReranker())

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What does Knowmate do?", "mode": "vector_only"},
    )

    assert response.status_code == 200, response.text
    stages = {stage["name"]: stage for stage in response.json()["retrieval_trace"]["stages"]}
    rerank_output = stages["rerank"]["output"]
    assert rerank_output["original_threshold"] == 0.8
    assert rerank_output["degraded_threshold"] == 0.56
    assert rerank_output["mmr_input_count"] == 1
    assert rerank_output["mmr_output_count"] == 1


def test_quick_answer_response_includes_prompt_context_summary(client, db_session, fake_vector_store):
    kb_id = create_kb(client)
    add_completed_document(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-quick-trace",
            "knowledge_id": "doc-quick-trace",
            "knowledge_base_id": kb_id,
            "content": "Knowmate answers from private documents.",
            "title": "Quick Trace Doc",
            "score": 0.91,
        }
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What does Knowmate do?", "mode": "vector_only", "top_k": 5},
    )

    assert response.status_code == 200, response.text
    trace = response.json()["retrieval_trace"]
    assert trace["prompt_context_summary"]
    assert "Quick Trace Doc" in trace["prompt_context_summary"]
    assert trace["context_chunk_ids"] == ["chunk-quick-trace"]
    assert trace["context_char_count"] > 0
    assert trace["context_truncated"] is False


def test_quick_answer_uses_text_attachment_context_without_sources(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = []

    response = client.post(
        "/api/v1/quick-answer",
        json={
            "knowledge_base_id": kb_id,
            "query": "附件里的专属代号是什么？",
            "mode": "vector_only",
            "attachments": [
                {
                    "filename": "note.txt",
                    "mime_type": "text/plain",
                    "content": "附件事实：专属代号是 KM-ATTACH-42。",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "KM-ATTACH-42" in payload["answer"]
    assert payload["sources"] == []
    trace = payload["retrieval_trace"]
    assert trace["attachments_used"] is True
    assert trace["attachments"][0]["filename"] == "note.txt"
    assert trace["attachments"][0]["truncated"] is False
    assert "<attachments>" in trace["rendered_context"]
    assert "KM-ATTACH-42" not in str(payload["sources"])


def test_quick_answer_rejects_oversized_attachment_with_chinese_error(client, fake_vector_store):
    kb_id = create_kb(client)
    fake_vector_store.results = []

    response = client.post(
        "/api/v1/quick-answer",
        json={
            "knowledge_base_id": kb_id,
            "query": "附件是什么？",
            "mode": "vector_only",
            "attachments": [{"filename": "too-large.txt", "content": "甲" * 70000}],
        },
    )

    assert response.status_code == 400
    assert "附件 too-large.txt 超过大小限制" in response.text


def test_conversation_context_truncates_long_history():
    history = [
        ChatMessage(role="user", content="第一轮" + "甲" * 200, status="completed"),
        ChatMessage(role="assistant", content="第一答" + "乙" * 200, status="completed"),
        ChatMessage(role="user", content="第二轮" + "丙" * 200, status="completed"),
    ]

    context, trace = _build_conversation_context(history, max_messages=2, max_chars=80)

    assert "第一轮" not in context
    assert "第二轮" in context
    assert trace["history_used"] is True
    assert trace["history_message_count"] == 2
    assert trace["history_truncated"] is True
    assert trace["history_char_count"] > len(context)


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
    stages = {stage["name"]: stage for stage in payload["retrieval_trace"]["stages"]}
    assert stages["answer"]["status"] == "skipped"
    assert stages["answer"]["error_message"] == "没有在知识库中找到可引用的内容。"
    assert payload["retrieval_trace"]["prompt_context_summary"] == ""
    assert payload["retrieval_trace"]["context_chunk_ids"] == []
