from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models import Chunk, Knowledge
from app.main import create_app
from app.services.document_processing import DocumentProcessingService


def test_knowledge_upload_processing_and_quick_answer_flow(
    client: TestClient,
    db_session,
    fake_embedder,
    fake_chat_model,
    fake_vector_store,
    monkeypatch,
    tmp_path: Path,
):
    holder = {}

    def run_processing_now(document_id: str) -> None:
        with holder["app"].state.session_factory() as session:
            DocumentProcessingService(
                db=session,
                upload_dir=tmp_path,
                embedder=fake_embedder,
                vector_store=fake_vector_store,
            ).process(document_id)

    monkeypatch.setattr(
        "app.workers.tasks.enqueue_document_processing",
        run_processing_now,
    )

    app = create_app(
        settings=client.app.state.settings,
        session_factory=client.app.state.session_factory,
        embedder=fake_embedder,
        chat_model=fake_chat_model,
        vector_store=fake_vector_store,
    )
    holder["app"] = app
    local_client = TestClient(app)
    create_response = local_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Knowmate KB", "description": "Test knowledge base"},
    )
    assert create_response.status_code == 201
    kb_id = create_response.json()["id"]

    upload_response = local_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("intro.txt", b"Knowmate is a FastAPI RAG assistant.", "text/plain")},
    )
    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["parse_status"] == "pending"

    document_response = local_client.get(f"/api/v1/documents/{document['id']}")
    assert document_response.status_code == 200
    assert document_response.json()["parse_status"] == "completed"

    chunks_response = local_client.get(f"/api/v1/documents/{document['id']}/chunks")
    assert chunks_response.status_code == 200
    assert len(chunks_response.json()) == 1

    answer_response = local_client.post(
        "/api/v1/quick-answer",
        json={"knowledge_base_id": kb_id, "query": "What is Knowmate?", "top_k": 3},
    )
    assert answer_response.status_code == 200
    payload = answer_response.json()
    assert payload["answer"] == "Knowmate is a FastAPI RAG assistant."
    assert payload["sources"][0]["document_id"] == document["id"]
    assert payload["sources"][0]["content"] == "Knowmate is a FastAPI RAG assistant."

    db_document = db_session.get(Knowledge, document["id"])
    assert db_document is not None
    assert db_document.parse_status == "completed"
    assert db_session.query(Chunk).filter_by(knowledge_id=document["id"]).count() == 1
