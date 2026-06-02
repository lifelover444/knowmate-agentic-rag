from pathlib import Path

from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge, ProcessingTask


def create_kb(client: TestClient, name: str, embedding_model_id: str | None = None) -> tuple[str, str]:
    chat_id, default_embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": name,
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_model_id or default_embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], response.json()["embedding_model_id"]


def add_document(db_session, kb_id: str, file_path: str, *, status: str = "completed") -> Knowledge:
    document = Knowledge(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        type="file",
        source_type="file",
        title="lifecycle.txt",
        source="upload",
        parse_status=status,
        enable_status="enabled",
        embedding_model_id="embedding-model",
        file_name="lifecycle.txt",
        file_type="txt",
        file_path=file_path,
        file_size=12,
        storage_size=12,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def add_chunk(db_session, document: Knowledge) -> Chunk:
    chunk = Chunk(
        tenant_id=document.tenant_id,
        knowledge_base_id=document.knowledge_base_id,
        knowledge_id=document.id,
        content="生命周期测试内容",
        search_text="生命周期测试内容",
        chunk_index=0,
        is_enabled=True,
        start_at=0,
        end_at=8,
        chunk_type="text",
        context_header=None,
        chunk_metadata={"title": document.title},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


def test_document_download_returns_original_file(client: TestClient, db_session, tmp_path: Path):
    kb_id, _ = create_kb(client, "download kb")
    file_path = tmp_path / "lifecycle.txt"
    file_path.write_text("download me", encoding="utf-8")
    document = add_document(db_session, kb_id, str(file_path))

    response = client.get(f"/api/v1/documents/{document.id}/download")

    assert response.status_code == 200, response.text
    assert response.content == b"download me"
    assert "attachment" in response.headers["content-disposition"]
    assert "lifecycle.txt" in response.headers["content-disposition"]


def test_cancel_parse_marks_document_task_and_timeline_cancelled(client: TestClient, db_session, tmp_path: Path):
    kb_id, _ = create_kb(client, "cancel kb")
    file_path = tmp_path / "cancel.txt"
    file_path.write_text("cancel me", encoding="utf-8")
    document = add_document(db_session, kb_id, str(file_path), status="processing")
    task = ProcessingTask(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        document_id=document.id,
        task_type="document_upload_process",
        status="processing",
        progress=30,
    )
    db_session.add(task)
    db_session.commit()

    response = client.post(f"/api/v1/documents/{document.id}/cancel-parse")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["parse_status"] == "cancelled"
    assert payload["error_message"] == "用户已取消解析"
    persisted_task = db_session.get(ProcessingTask, task.id)
    assert persisted_task.status == "cancelled"
    assert persisted_task.error_message == "用户已取消解析"

    timeline = client.get(f"/api/v1/documents/{document.id}/spans").json()
    assert timeline["root"]["status"] == "cancelled"
    assert {stage["status"] for stage in timeline["stages"]} == {"cancelled"}


def test_move_document_updates_document_chunks_and_vector_payload(
    client: TestClient,
    db_session,
    tmp_path: Path,
    fake_vector_store,
):
    source_kb_id, embedding_id = create_kb(client, "source kb")
    target_kb_id, _ = create_kb(client, "target kb", embedding_model_id=embedding_id)
    file_path = tmp_path / "move.txt"
    file_path.write_text("move me", encoding="utf-8")
    document = add_document(db_session, source_kb_id, str(file_path))
    chunk = add_chunk(db_session, document)
    document_id = document.id
    chunk_id = chunk.id
    fake_vector_store.points.append(
        {
            "vector": [1.0, 0.0, 0.0],
            "payload": {
                "knowledge_id": document_id,
                "knowledge_base_id": source_kb_id,
                "chunk_id": chunk_id,
                "content": chunk.content,
            },
        }
    )

    response = client.post(
        "/api/v1/documents/move",
        json={"document_ids": [document_id], "target_kb_id": target_kb_id},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "requested": 1,
        "moved": 1,
        "failed": 0,
        "failures": [],
        "target_kb_id": target_kb_id,
    }
    moved_document = db_session.get(Knowledge, document_id)
    moved_chunk = db_session.get(Chunk, chunk_id)
    assert moved_document.knowledge_base_id == target_kb_id
    assert moved_chunk.knowledge_base_id == target_kb_id
    assert fake_vector_store.points[0]["payload"]["knowledge_base_id"] == target_kb_id


def test_move_document_rejects_incompatible_embedding_model(client: TestClient, db_session, tmp_path: Path):
    source_kb_id, _ = create_kb(client, "source mismatch kb")
    target_kb_id, _ = create_kb(client, "target mismatch kb")
    file_path = tmp_path / "mismatch.txt"
    file_path.write_text("mismatch", encoding="utf-8")
    document = add_document(db_session, source_kb_id, str(file_path))

    response = client.post(
        "/api/v1/documents/move",
        json={"document_ids": [document.id], "target_kb_id": target_kb_id},
    )

    assert response.status_code == 400, response.text
    assert "目标知识库必须使用相同的 Embedding 模型" in response.text
