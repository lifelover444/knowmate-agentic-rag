from pathlib import Path

from app.db.models import Chunk, KnowledgeBase
from app.services.document_processing import DocumentProcessingService


def test_document_processing_uses_context_headers_and_parent_child_payloads(
    client,
    db_session,
    fake_embedder,
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

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    holder["app"] = client.app

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "Chunk Context KB",
            "chunking_config": {
                "strategy": "heading",
                "chunk_size": 180,
                "chunk_overlap": 20,
                "enable_parent_child": True,
                "parent_chunk_size": 512,
                "child_chunk_size": 120,
            },
        },
    )
    assert create_response.status_code == 201
    kb_id = create_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={
            "file": (
                "manual.md",
                ("# 手册\n\n## 安装\n" + "安装内容。" * 80 + "\n\n## 使用\n" + "使用内容。" * 80).encode(),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 201

    chunks = db_session.query(Chunk).filter_by(knowledge_base_id=kb_id).order_by(Chunk.chunk_index).all()
    assert any(chunk.chunk_type == "parent" for chunk in chunks)
    child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]
    assert child_chunks
    assert all(chunk.parent_chunk_id for chunk in child_chunks)
    assert any(chunk.context_header and "## 安装" in chunk.context_header for chunk in child_chunks)

    payload = fake_vector_store.points[0]["payload"]
    assert payload["chunk_type"] == "child"
    assert payload["context_header"]
    assert payload["parent_chunk_id"]
    assert "metadata" in payload

    kb = db_session.get(KnowledgeBase, kb_id)
    assert kb is not None
    assert kb.chunking_config["strategy"] == "heading"
    assert kb.parser_engine_rules
