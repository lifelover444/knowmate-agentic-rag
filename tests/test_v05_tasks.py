from conftest import create_bound_models
from fastapi.testclient import TestClient


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "v0.5 task KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_document_upload_creates_processing_task(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("task.txt", b"task center content", "text/plain")},
    )

    assert response.status_code == 201, response.text
    document_id = response.json()["id"]
    assert enqueued == [document_id]

    tasks_response = client.get("/api/v1/tasks")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) == 1
    assert tasks[0]["document_id"] == document_id
    assert tasks[0]["knowledge_base_id"] == kb_id
    assert tasks[0]["task_type"] == "document_upload_process"
    assert tasks[0]["status"] == "queued"
    assert tasks[0]["progress"] == 0


def test_document_reprocess_and_kb_rebuild_enqueue_tasks(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("reprocess.txt", b"reprocess content", "text/plain")},
    )
    document_id = upload_response.json()["id"]
    enqueued.clear()

    reprocess_response = client.post(f"/api/v1/documents/{document_id}/reprocess")
    assert reprocess_response.status_code == 202, reprocess_response.text
    assert reprocess_response.json()["id"] == document_id
    assert enqueued == [document_id]

    rebuild_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/reprocess")
    assert rebuild_response.status_code == 202, rebuild_response.text
    assert rebuild_response.json()["queued"] == 1
    assert enqueued == [document_id, document_id]

    tasks = client.get("/api/v1/tasks").json()
    assert [task["task_type"] for task in tasks] == [
        "knowledge_base_rebuild",
        "document_reprocess",
        "document_upload_process",
    ]


def test_failed_task_can_be_retried(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("retry.txt", b"retry content", "text/plain")},
    )
    document_id = upload_response.json()["id"]
    task = client.get("/api/v1/tasks").json()[0]

    from app.db.models import ProcessingTask

    with client.app.state.session_factory() as session:
        db_task = session.get(ProcessingTask, task["id"])
        db_task.status = "failed"
        db_task.error_message = "测试失败"
        db_task.progress = 20
        session.commit()

    retry_response = client.post(f"/api/v1/tasks/{task['id']}/retry")

    assert retry_response.status_code == 202, retry_response.text
    payload = retry_response.json()
    assert payload["status"] == "queued"
    assert payload["error_message"] is None
    assert payload["progress"] == 0
    assert enqueued == [document_id, document_id]
