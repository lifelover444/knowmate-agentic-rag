from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge
from app.main import create_app


def _create_kb_with_models(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "rerank required KB", "embedding_model_id": embedding_id, "summary_model_id": chat_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _add_completed_document(db_session, kb_id: str) -> None:
    db_session.add(
        Knowledge(
            id="doc-rerank-required",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            type="file",
            title="rerank required",
            source="upload",
            parse_status="completed",
            enable_status="enabled",
            file_size=0,
            storage_size=0,
        )
    )
    db_session.add(
        Chunk(
            id="chunk-rerank-required",
            tenant_id=10000,
            knowledge_base_id=kb_id,
            knowledge_id="doc-rerank-required",
            content="rerank is mandatory for v0.9 quick answer",
            search_text="rerank mandatory quick answer",
            chunk_index=0,
            start_at=0,
            end_at=42,
            chunk_type="child",
        )
    )
    db_session.commit()


def test_knowledge_base_create_requires_model_config(
    client: TestClient,
    fake_vector_store,
):
    app = create_app(
        settings=client.app.state.settings,
        session_factory=client.app.state.session_factory,
        vector_store=fake_vector_store,
    )
    local_client = TestClient(app)

    response = local_client.post("/api/v1/knowledge-bases", json={"name": "KB"})

    assert response.status_code == 400
    assert "请先配置并测试模型" in response.text


def test_quick_answer_rejects_unknown_knowledge_base_without_model_config(client: TestClient, fake_vector_store):
    app = create_app(
        settings=client.app.state.settings,
        session_factory=client.app.state.session_factory,
        vector_store=fake_vector_store,
    )
    local_client = TestClient(app)
    response = local_client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": "missing-kb", "query": "知友能做什么？"},
    )

    assert response.status_code == 404
    assert "knowledge base not found" in response.text


def test_quick_answer_requires_rerank_model_config(client: TestClient, db_session, fake_vector_store):
    kb_id = _create_kb_with_models(client)
    _add_completed_document(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-rerank-required",
            "knowledge_id": "doc-rerank-required",
            "knowledge_base_id": kb_id,
            "content": "rerank is mandatory for v0.9 quick answer",
            "score": 0.91,
            "chunk_type": "child",
        }
    ]

    response = client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "rerank required", "enable_rerank": False},
    )

    assert response.status_code == 400
    assert "系统未完成 rerank 模型配置" in response.text


def test_stream_quick_answer_requires_rerank_model_config(client: TestClient, db_session, fake_vector_store):
    kb_id = _create_kb_with_models(client)
    _add_completed_document(db_session, kb_id)
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-rerank-required",
            "knowledge_id": "doc-rerank-required",
            "knowledge_base_id": kb_id,
            "content": "rerank is mandatory for v0.9 quick answer",
            "score": 0.91,
            "chunk_type": "child",
        }
    ]

    response = client.post(
        "/api/v1/quick-answer/stream",
        json={"knowledge_base_id": kb_id, "query": "rerank required", "enable_rerank": False},
    )

    assert response.status_code == 400
    assert "系统未完成 rerank 模型配置" in response.text
