from pathlib import Path

import pytest
from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Knowledge
from app.services.document_processing import DocumentProcessingService


def create_kb(client: TestClient) -> str:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "span KB", "summary_model_id": chat_id, "embedding_model_id": embedding_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_document(db_session, kb_id: str, file_path: str, status: str = "pending") -> str:
    document = Knowledge(
        tenant_id=10000,
        knowledge_base_id=kb_id,
        type="file",
        title="span doc",
        source="upload",
        parse_status=status,
        enable_status="enabled",
        file_name="span.txt",
        file_type="txt",
        file_path=file_path,
        file_size=0,
        storage_size=0,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document.id


class BrokenEmbedder:
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding service unavailable")


def test_document_processing_spans_success_timeline(
    client: TestClient,
    db_session,
    tmp_path: Path,
    fake_vector_store,
    fake_embedder,
):
    kb_id = create_kb(client)
    path = tmp_path / "span.txt"
    path.write_text("一段用于处理 timeline 的内容。", encoding="utf-8")
    document_id = add_document(db_session, kb_id, str(path))

    DocumentProcessingService(db_session, tmp_path, fake_vector_store, embedder=fake_embedder).process(document_id)

    response = client.get(f"/api/v1/documents/{document_id}/spans")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["attempt"] == 1
    assert payload["root"]["status"] == "done"
    assert [stage["name"] for stage in payload["stages"]] == ["parse", "chunk", "embed", "upsert", "finalize"]
    assert {stage["status"] for stage in payload["stages"]} == {"done"}
    assert all(stage["duration_ms"] >= 0 for stage in payload["stages"])


def test_document_processing_spans_failure_cancels_downstream(
    client: TestClient,
    db_session,
    tmp_path: Path,
    fake_vector_store,
):
    kb_id = create_kb(client)
    document_id = add_document(db_session, kb_id, str(tmp_path / "missing.txt"))

    with pytest.raises(FileNotFoundError):
        DocumentProcessingService(db_session, tmp_path, fake_vector_store, embedder=None).process(document_id)

    response = client.get(f"/api/v1/documents/{document_id}/spans")
    assert response.status_code == 200, response.text
    stages = response.json()["stages"]
    assert stages[0]["name"] == "parse"
    assert stages[0]["status"] == "failed"
    assert "missing.txt" in stages[0]["error_message"]
    assert [stage["status"] for stage in stages[1:]] == ["cancelled", "cancelled", "cancelled", "cancelled"]


def test_document_processing_spans_embedding_failure_cancels_downstream(
    client: TestClient,
    db_session,
    tmp_path: Path,
    fake_vector_store,
):
    kb_id = create_kb(client)
    path = tmp_path / "span.txt"
    path.write_text("一段会在 embedding 阶段失败的内容。", encoding="utf-8")
    document_id = add_document(db_session, kb_id, str(path))

    with pytest.raises(RuntimeError, match="embedding service unavailable"):
        service = DocumentProcessingService(db_session, tmp_path, fake_vector_store, embedder=BrokenEmbedder())
        service.process(document_id)

    response = client.get(f"/api/v1/documents/{document_id}/spans")
    assert response.status_code == 200, response.text
    stages = response.json()["stages"]
    assert [stage["status"] for stage in stages] == ["done", "done", "failed", "cancelled", "cancelled"]
    assert stages[2]["name"] == "embed"
    assert stages[2]["error_message"] == "embedding service unavailable"


def test_document_spans_returns_safe_placeholders_for_legacy_document(client: TestClient, db_session, tmp_path: Path):
    kb_id = create_kb(client)
    document_id = add_document(db_session, kb_id, "", status="completed")

    response = client.get(f"/api/v1/documents/{document_id}/spans")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["attempt"] == 0
    assert payload["root"]["status"] == "done"
    assert [stage["status"] for stage in payload["stages"]] == ["done", "done", "done", "done", "done"]
