from fastapi.testclient import TestClient

from app.main import create_app


def test_document_upload_requires_model_config(
    client: TestClient,
    fake_vector_store,
):
    app = create_app(
        settings=client.app.state.settings,
        session_factory=client.app.state.session_factory,
        vector_store=fake_vector_store,
    )
    local_client = TestClient(app)

    kb_response = local_client.post("/api/v1/knowledge-bases", json={"name": "KB"})
    document_response = local_client.post(
        f"/api/v1/knowledge-bases/{kb_response.json()['id']}/documents/file",
        files={"file": ("intro.txt", b"Knowmate needs real model config.", "text/plain")},
    )

    assert document_response.status_code == 400
    assert "请先配置并测试模型" in document_response.text


def test_quick_answer_requires_model_config(client: TestClient, fake_vector_store):
    app = create_app(
        settings=client.app.state.settings,
        session_factory=client.app.state.session_factory,
        vector_store=fake_vector_store,
    )
    local_client = TestClient(app)
    kb_response = local_client.post("/api/v1/knowledge-bases", json={"name": "KB"})

    response = local_client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_response.json()["id"], "query": "知友能做什么？"},
    )

    assert response.status_code == 400
    assert "请先配置并测试模型" in response.text
