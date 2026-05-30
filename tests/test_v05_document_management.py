from conftest import create_bound_models
from fastapi.testclient import TestClient


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "documents v0.5", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_document_list_filters_and_exposes_task_status(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("alpha.txt", b"alpha text", "text/plain")},
    )
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("beta.md", b"# beta", "text/markdown")},
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        params={"file_type": "md", "keyword": "beta", "status": "pending"},
    )

    assert response.status_code == 200
    documents = response.json()
    assert len(documents) == 1
    assert documents[0]["file_name"] == "beta.md"
    assert documents[0]["chunk_count"] == 0
    assert documents[0]["task_status"] == "queued"


def test_batch_reprocess_and_delete_documents(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)
    first = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("first.txt", b"first", "text/plain")},
    ).json()
    second = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("second.txt", b"second", "text/plain")},
    ).json()
    enqueued.clear()

    reprocess_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch-reprocess",
        json={"document_ids": [first["id"], second["id"]]},
    )
    assert reprocess_response.status_code == 202, reprocess_response.text
    assert reprocess_response.json()["queued"] == 2
    assert enqueued == [first["id"], second["id"]]

    delete_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch-delete",
        json={"document_ids": [first["id"], second["id"]]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 2
    assert client.get(f"/api/v1/knowledge-bases/{kb_id}/documents").json() == []


def test_manual_text_import_enters_processing_tasks(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/text",
        json={"title": "在线文本", "content": "这是一段 markdown 在线录入内容", "format": "markdown"},
    )

    assert response.status_code == 201, response.text
    document = response.json()
    assert document["source_type"] == "manual_text"
    assert document["file_type"] == "md"
    assert enqueued == [document["id"]]


def test_url_import_rejects_localhost(client: TestClient):
    kb_id = _create_kb(client)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/url",
        json={"url": "http://127.0.0.1/private"},
    )

    assert response.status_code == 400
    assert "不支持导入本地或内网地址" in response.text
