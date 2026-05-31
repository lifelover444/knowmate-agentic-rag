from datetime import UTC, datetime

from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ChatMessage, Chunk, FAQEntry, Knowledge


def create_kb(client: TestClient, name: str = "chat experience KB") -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name, "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_session(client: TestClient, kb_id: str, title: str) -> dict:
    response = client.post("/api/v1/chat-sessions", json={"knowledge_base_id": kb_id, "title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_chat_sessions_can_search_title_and_message_content(client: TestClient, db_session):
    kb_id = create_kb(client)
    refund = create_session(client, kb_id, "退款政策讨论")
    onboarding = create_session(client, kb_id, "入门说明")
    db_session.add(
        ChatMessage(
            tenant_id=10000,
            session_id=onboarding["id"],
            role="user",
            content="如何上传合同资料？",
            status="completed",
        )
    )
    db_session.commit()

    title_response = client.get("/api/v1/chat-sessions", params={"keyword": "退款"})
    assert title_response.status_code == 200, title_response.text
    assert [item["id"] for item in title_response.json()["items"]] == [refund["id"]]

    message_response = client.get("/api/v1/chat-sessions", params={"keyword": "合同"})
    assert message_response.status_code == 200, message_response.text
    assert [item["id"] for item in message_response.json()["items"]] == [onboarding["id"]]


def test_chat_session_batch_delete_returns_partial_failure_summary(client: TestClient):
    kb_id = create_kb(client)
    first = create_session(client, kb_id, "第一轮")
    second = create_session(client, kb_id, "第二轮")

    response = client.post(
        "/api/v1/chat-sessions/batch-delete",
        json={"session_ids": [first["id"], "missing-session", second["id"]]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["requested"] == 3
    assert payload["deleted"] == 2
    assert payload["failed"] == 1
    assert payload["failures"] == [{"session_id": "missing-session", "reason": "chat session not found"}]
    assert client.get("/api/v1/chat-sessions").json()["items"] == []


def test_chat_recommended_questions_come_from_faq_and_generated_chunk_questions(client: TestClient, db_session):
    kb_id = create_kb(client)
    now = datetime.now(UTC)
    faq_knowledge = Knowledge(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        type="faq",
        source_type="faq",
        title="FAQ",
        source="manual",
        parse_status="completed",
        file_size=0,
        storage_size=0,
        created_at=now,
        updated_at=now,
    )
    document = Knowledge(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        type="document",
        source_type="file",
        title="入门手册",
        source="manual.md",
        parse_status="completed",
        file_size=0,
        storage_size=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([faq_knowledge, document])
    db_session.flush()
    db_session.add(
        FAQEntry(
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=faq_knowledge.id,
            question="如何申请退款？",
            answer="联系售后处理。",
            enabled=True,
        )
    )
    db_session.add(
        Chunk(
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id=document.id,
            content="上传文档后系统会自动解析并切分。",
            search_text="上传文档后系统会自动解析并切分。",
            chunk_index=0,
            is_enabled=True,
            start_at=0,
            end_at=16,
            chunk_type="text",
            chunk_metadata={"generated_questions": [{"question": "上传文档后会发生什么？"}]},
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/chat-sessions/recommended-questions",
        params={"knowledge_base_id": kb_id, "limit": 5},
    )

    assert response.status_code == 200, response.text
    questions = response.json()["items"]
    assert [item["question"] for item in questions] == ["如何申请退款？", "上传文档后会发生什么？"]
    assert questions[0]["source_type"] == "faq"
    assert questions[1]["source_type"] == "chunk"
