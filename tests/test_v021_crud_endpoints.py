from conftest import create_bound_models
from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge, KnowledgeBase


def create_knowledge_base(client: TestClient, name: str) -> dict:
    chat_id, embedding_id = create_bound_models(client)
    response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": name,
            "description": f"{name} description",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_knowledge_base_list_update_and_soft_delete(client: TestClient, db_session):
    first = create_knowledge_base(client, "first KB")
    second = create_knowledge_base(client, "second KB")

    list_response = client.get("/api/v1/knowledge-bases")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [second["id"], first["id"]]

    update_response = client.put(
        f"/api/v1/knowledge-bases/{first['id']}",
        json={"name": "renamed KB", "description": "updated description"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "renamed KB"
    assert update_response.json()["description"] == "updated description"
    assert update_response.json()["embedding_model_id"] == first["embedding_model_id"]

    delete_response = client.delete(f"/api/v1/knowledge-bases/{first['id']}")
    assert delete_response.status_code == 204

    assert client.get(f"/api/v1/knowledge-bases/{first['id']}").status_code == 404
    list_after_delete = client.get("/api/v1/knowledge-bases")
    assert [item["id"] for item in list_after_delete.json()] == [second["id"]]

    db_kb = db_session.get(KnowledgeBase, first["id"])
    assert db_kb.deleted_at is not None


def test_knowledge_base_documents_list_and_document_soft_delete(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb = create_knowledge_base(client, "documents KB")
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)

    first_upload = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/file",
        files={"file": ("first.txt", b"first document", "text/plain")},
    )
    second_upload = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/file",
        files={"file": ("second.txt", b"second document", "text/plain")},
    )
    assert first_upload.status_code == 201
    assert second_upload.status_code == 201
    first_document_id = first_upload.json()["id"]
    second_document_id = second_upload.json()["id"]

    db_session.add(
        Chunk(
            tenant_id=kb["tenant_id"],
            knowledge_base_id=kb["id"],
            knowledge_id=first_document_id,
            content="first chunk",
            chunk_index=0,
            start_at=0,
            end_at=11,
        )
    )
    db_session.commit()
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-1",
            "knowledge_id": first_document_id,
            "knowledge_base_id": kb["id"],
            "content": "first chunk",
            "score": 1.0,
        }
    ]

    documents_response = client.get(f"/api/v1/knowledge-bases/{kb['id']}/documents")
    assert documents_response.status_code == 200
    assert [item["id"] for item in documents_response.json()] == [second_document_id, first_document_id]

    delete_document_response = client.delete(f"/api/v1/documents/{first_document_id}")
    assert delete_document_response.status_code == 204

    assert client.get(f"/api/v1/documents/{first_document_id}").status_code == 404
    remaining_documents = client.get(f"/api/v1/knowledge-bases/{kb['id']}/documents").json()
    assert [item["id"] for item in remaining_documents] == [second_document_id]
    assert db_session.get(Knowledge, first_document_id).deleted_at is not None
    deleted_chunk = db_session.query(Chunk).filter_by(knowledge_id=first_document_id).one()
    assert deleted_chunk.deleted_at is not None
    assert deleted_chunk.is_enabled is False


def test_knowledge_base_soft_delete_deletes_documents_and_vectors(
    client: TestClient,
    db_session,
    fake_vector_store,
    monkeypatch,
):
    kb = create_knowledge_base(client, "delete cascade KB")
    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", lambda document_id: None)

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/file",
        files={"file": ("intro.txt", b"delete me", "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]
    fake_vector_store.results = [
        {
            "chunk_id": "chunk-1",
            "knowledge_id": document_id,
            "knowledge_base_id": kb["id"],
            "content": "delete me",
            "score": 1.0,
        }
    ]

    delete_response = client.delete(f"/api/v1/knowledge-bases/{kb['id']}")
    assert delete_response.status_code == 204

    assert client.get(f"/api/v1/knowledge-bases/{kb['id']}/documents").status_code == 404
    assert db_session.get(KnowledgeBase, kb["id"]).deleted_at is not None
    assert db_session.get(Knowledge, document_id).deleted_at is not None
    assert fake_vector_store.results == []
