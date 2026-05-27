from fastapi.testclient import TestClient

from app.main import create_app


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
