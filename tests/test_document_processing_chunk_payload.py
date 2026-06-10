from pathlib import Path

from conftest import create_bound_models

from app.db.models import Chunk, KnowledgeBase
from app.db.repositories.chunk import ChunkRepository
from app.rag.parser import ParsedDocument
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
    chat_id, embedding_id = create_bound_models(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "Chunk Context KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
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
    first_child = child_chunks[0]
    assert first_child.search_text
    assert first_child.content in first_child.search_text
    assert first_child.created_at is not None
    assert first_child.updated_at is not None
    assert first_child.chunk_metadata["tenant_id"] == 10000
    assert first_child.chunk_metadata["knowledge_base_id"] == kb_id
    assert first_child.chunk_metadata["document_id"] == upload_response.json()["id"]
    assert first_child.chunk_metadata["child_chunk_id"] == first_child.id
    assert first_child.chunk_metadata["parent_chunk_id"] == first_child.parent_chunk_id
    assert first_child.chunk_metadata["chunk_type"] == "child"
    assert first_child.chunk_metadata["position"] == first_child.chunk_index
    assert first_child.chunk_metadata["normalized_content"] == first_child.search_text
    assert first_child.chunk_metadata["context_header"] == first_child.context_header

    payload = fake_vector_store.points[0]["payload"]
    assert payload["chunk_type"] == "child"
    assert payload["context_header"]
    assert payload["parent_chunk_id"]
    assert "metadata" in payload
    assert payload["tenant_id"] == 10000
    assert payload["document_id"] == upload_response.json()["id"]
    assert payload["child_chunk_id"] == payload["chunk_id"]
    assert payload["search_text"]
    assert payload["position"] >= 0
    assert payload["metadata"]["normalized_content"] == payload["search_text"]

    kb = db_session.get(KnowledgeBase, kb_id)
    assert kb is not None
    assert kb.chunking_config["strategy"] == "auto"
    assert kb.parser_engine_rules


def test_document_processing_ignores_legacy_parent_child_disable(
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
    chat_id, embedding_id = create_bound_models(client)
    bm25_upserts = []

    def track_bm25_upsert(self, chunks):
        bm25_upserts.append([chunk.chunk_type for chunk in chunks])
        return chunks

    monkeypatch.setattr(ChunkRepository, "bm25_upsert_chunks", track_bm25_upsert)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "Legacy Disable KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
            "chunking_config": {
                "strategy": "legacy",
                "chunk_size": 180,
                "chunk_overlap": 20,
                "enable_parent_child": False,
                "parent_chunk_size": 512,
                "child_chunk_size": 120,
            },
        },
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["chunking_config"]["enable_parent_child"] is True
    kb_id = create_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={
            "file": (
                "legacy-disable.md",
                ("# 总览\n\n## 第一节\n" + "第一节内容。" * 80 + "\n\n## 第二节\n" + "第二节内容。" * 80).encode(),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 201, upload_response.text

    chunks = db_session.query(Chunk).filter_by(knowledge_base_id=kb_id).order_by(Chunk.chunk_index).all()
    assert any(chunk.chunk_type == "parent" for chunk in chunks)
    assert any(chunk.chunk_type == "child" and chunk.parent_chunk_id for chunk in chunks)
    assert not any(chunk.chunk_type == "text" for chunk in chunks)
    assert fake_vector_store.points
    assert all(point["payload"]["chunk_type"] == "child" for point in fake_vector_store.points)
    assert bm25_upserts
    assert bm25_upserts[0]
    assert set(bm25_upserts[0]) == {"child"}


def test_document_processing_marks_failed_when_bm25_upsert_fails(
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
            try:
                DocumentProcessingService(
                    db=session,
                    upload_dir=tmp_path,
                    embedder=fake_embedder,
                    vector_store=fake_vector_store,
                ).process(document_id)
            except RuntimeError:
                pass

    def fail_bm25_upsert(self, chunks):
        raise RuntimeError("ParadeDB BM25 写入失败：索引不可用")

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    monkeypatch.setattr(ChunkRepository, "bm25_upsert_chunks", fail_bm25_upsert)
    holder["app"] = client.app
    chat_id, embedding_id = create_bound_models(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "BM25 Failure KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    kb_id = create_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("bm25-fail.md", ("# BM25\n\n" + "失败路径。" * 120).encode(), "text/markdown")},
    )

    assert upload_response.status_code == 201, upload_response.text
    document = db_session.get(KnowledgeBase, kb_id).documents[0]
    assert document.parse_status == "failed"
    assert "ParadeDB BM25 写入失败" in document.error_message
    assert fake_vector_store.points == []


def test_document_processing_fails_empty_parsed_content_with_ocr_guidance(
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
            try:
                DocumentProcessingService(
                    db=session,
                    upload_dir=tmp_path,
                    embedder=fake_embedder,
                    vector_store=fake_vector_store,
                ).process(document_id)
            except ValueError:
                pass

    def empty_parse(self, path, engine=None):
        return ParsedDocument(
            title=path.name,
            content="",
            metadata={"file_type": "pdf", "page_count": 2},
            pages=[{"page": 1, "start": 0, "end": 0}, {"page": 2, "start": 0, "end": 0}],
        )

    monkeypatch.setattr("app.workers.tasks.enqueue_document_processing", run_processing_now)
    monkeypatch.setattr("app.services.document_processing.DocumentParser.parse", empty_parse)
    holder["app"] = client.app
    chat_id, embedding_id = create_bound_models(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "Empty PDF KB",
            "summary_model_id": chat_id,
            "embedding_model_id": embedding_id,
        },
    )
    assert create_response.status_code == 201, create_response.text
    kb_id = create_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents/file",
        files={"file": ("empty.pdf", b"%PDF-empty", "application/pdf")},
    )

    assert upload_response.status_code == 201, upload_response.text
    document = db_session.get(KnowledgeBase, kb_id).documents[0]
    assert document.parse_status == "failed"
    assert "未解析出可入库文本" in document.error_message
    assert "OCR" in document.error_message
    assert db_session.query(Chunk).filter_by(knowledge_id=document.id).count() == 0
    assert fake_vector_store.points == []
