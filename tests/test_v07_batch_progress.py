from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import ProcessingTask


def _create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "batch progress KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_document(client: TestClient, kb_id: str, name: str) -> dict:
    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": (name, f"batch progress content for {name}".encode(), "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_batch_reprocess_reports_partial_failures_and_task_summary(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    enqueued: list[str] = []
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", enqueued.append)
    first = _upload_document(client, kb_id, "first.txt")
    second = _upload_document(client, kb_id, "second.txt")
    enqueued.clear()

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch-reprocess",
        json={"document_ids": [first["id"], "missing-document", second["id"]]},
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["requested"] == 3
    assert payload["queued"] == 2
    assert payload["succeeded"] == 2
    assert payload["failed"] == 1
    assert payload["failures"] == [
        {"document_id": "missing-document", "reason": "文档不存在或不属于当前知识库"}
    ]
    assert enqueued == [first["id"], second["id"]]

    task_ids = payload["task_ids"]
    with client.app.state.session_factory() as session:
        session.get(ProcessingTask, task_ids[0]).status = "completed"
        failed_task = session.get(ProcessingTask, task_ids[1])
        failed_task.status = "failed"
        failed_task.error_message = "测试批处理失败"
        session.commit()

    tasks_response = client.get("/api/v1/tasks", params={"knowledge_base_id": kb_id})

    assert tasks_response.status_code == 200
    tasks = [task for task in tasks_response.json() if task["id"] in task_ids]
    assert len(tasks) == 2
    summary = tasks[0]["batch_summary"]
    assert summary["total"] == 2
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["failures"] == [
        {"task_id": task_ids[1], "document_id": second["id"], "error_message": "测试批处理失败"}
    ]

    detail_response = client.get(f"/api/v1/tasks/{task_ids[1]}")
    assert detail_response.status_code == 200
    assert detail_response.json()["batch_summary"]["failed"] == 1


def test_batch_delete_reports_partial_failures(client: TestClient, monkeypatch):
    kb_id = _create_kb(client)
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)
    first = _upload_document(client, kb_id, "delete-first.txt")

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/batch-delete",
        json={"document_ids": [first["id"], "missing-delete"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested"] == 2
    assert payload["deleted"] == 1
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1
    assert payload["failures"] == [
        {"document_id": "missing-delete", "reason": "文档不存在或不属于当前知识库"}
    ]
